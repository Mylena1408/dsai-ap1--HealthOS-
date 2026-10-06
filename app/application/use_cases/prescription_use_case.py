from datetime import datetime
from typing import Callable, Optional
import uuid

from app.application.dtos.common import Page
from app.application.dtos.pharmacy_dto import (
    DispensationCreateDTO, DispensationDTO, DispensationLineDTO, PatientMedicationDTO, PrescriptionCreateDTO,
    PrescriptionDTO, PrescriptionItemDTO,
)
from app.application.interfaces.appointment_repository import AppointmentRepository
from app.application.interfaces.medical_record_repository import MedicalRecordRepository, PatientDirectoryRepository
from app.application.interfaces.pharmacy_repository import PharmacyRepository, PrescriptionFilters
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.application.services.clinical_links import resolve_professional
from app.application.services.stock_service import StockService
from app.domain.entities.medical_record import AllergyStatus
from app.domain.entities.medication import Medication
from app.domain.entities.pharmacy import (
    CONTROLLED_MAX_QUANTITY, CatalogStatus, Dispensation, DispensationLine, ItemStatus, MovementType, Prescription,
    PrescriptionItem,
)
from app.domain.entities.professional import ProfessionalType
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError

MIN_OVERRIDE_REASON = 10


def allergy_matches(substance: str, medication: Medication) -> bool:
    """Correspondência didática por texto entre a alergia e o nome/princípio ativo."""
    allergen = substance.casefold().strip()
    names = (medication.name.casefold(), medication.generic_name.casefold())
    return any(allergen in name or name in allergen for name in names if name)


class PrescriptionUseCase:

    def __init__(self, repo: PharmacyRepository, directory: PatientDirectoryRepository,
                 professional_repo: ProfessionalRepository, appointment_repo: AppointmentRepository,
                 records: MedicalRecordRepository, stock: StockService, clock: Callable[[], datetime] = datetime.now,
                 events: EventPublisher = NullPublisher()):
        self.repo = repo
        self.events = events
        self.directory = directory
        self.professional_repo = professional_repo
        self.appointment_repo = appointment_repo
        self.records = records
        self.stock = stock
        self.clock = clock

    # ------------------------------------------------------------- prescrição

    async def prescribe(self, dto: PrescriptionCreateDTO) -> PrescriptionDTO:
        if not await self.directory.get(dto.patient_id):
            raise EntityNotFoundError("Paciente", dto.patient_id)
        await self._require_professional(dto.prescriber_id, ProfessionalType.DOCTOR, "prescrever")
        await resolve_professional(self.appointment_repo, self.professional_repo,
                                   dto.patient_id, dto.prescriber_id, dto.appointment_id)

        medications = await self.repo.medications_by_ids({i.medication_id for i in dto.items})
        for item in dto.items:
            medication = medications.get(item.medication_id)
            if not medication:
                raise EntityNotFoundError("Medicamento", item.medication_id)
            details = await self.repo.get_details(item.medication_id)
            if details and details.catalog_status == CatalogStatus.DISCONTINUED:
                raise BusinessRuleViolation(f"{medication.name} está descontinuado e não pode ser prescrito.")
            if medication.is_controlled_substance and item.quantity > CONTROLLED_MAX_QUANTITY:
                raise BusinessRuleViolation(
                    f"{medication.name} é de controle especial: no máximo {CONTROLLED_MAX_QUANTITY} unidades por receita.")
        await self._check_allergies(dto, medications)

        prescription = Prescription(
            patient_id=dto.patient_id, prescriber_id=dto.prescriber_id, appointment_id=dto.appointment_id,
            issued_at=self.clock(), notes=dto.notes,
            special_control=any(medications[i.medication_id].is_controlled_substance for i in dto.items),
            allergy_override_reason=dto.allergy_override_reason.strip() if dto.allergy_override_reason else None,
            items=[PrescriptionItem(**item.model_dump()) for item in dto.items],
        )
        response = (await self._prescription_dtos([await self.repo.save_prescription(prescription)]))[0]
        await self.events.publish(DomainEvent(
            event_type=EventType.PRESCRIPTION_ISSUED, occurred_at=response.issued_at, entity_type="Prescricao",
            entity_id=response.id, patient_id=response.patient_id, professional_id=response.prescriber_id,
            summary=f"Prescrição emitida por {response.prescriber_name} para {response.patient_name}: "
                    + "; ".join(f"{i.medication_name} ({i.quantity:g})" for i in response.items) + ".",
            data={"special_control": response.special_control,
                  "allergy_override": bool(response.allergy_override_reason)}))
        return response

    async def get(self, prescription_id: uuid.UUID) -> PrescriptionDTO:
        return (await self._prescription_dtos([await self._get(prescription_id)]))[0]

    async def search(self, filters: PrescriptionFilters) -> Page[PrescriptionDTO]:
        items, total = await self.repo.search_prescriptions(filters)
        return Page(items=await self._prescription_dtos(items), total=total, limit=filters.limit, offset=filters.offset)

    async def cancel(self, prescription_id: uuid.UUID, reason: str) -> PrescriptionDTO:
        prescription = await self._get(prescription_id)
        prescription.cancel(reason)
        response = (await self._prescription_dtos([await self.repo.save_prescription(prescription)]))[0]
        await self.events.publish(DomainEvent(
            event_type=EventType.PRESCRIPTION_CANCELLED, occurred_at=self.clock(), entity_type="Prescricao",
            entity_id=response.id, patient_id=response.patient_id, professional_id=response.prescriber_id,
            summary=f"Prescrição de {response.patient_name} cancelada: {reason}."))
        return response

    async def change_item(self, prescription_id: uuid.UUID, item_id: uuid.UUID, action: str,
                          reason: Optional[str] = None) -> PrescriptionDTO:
        prescription = await self._get(prescription_id)
        item = prescription.item(item_id)
        if action == "suspend":
            item.suspend(reason)
        elif action == "resume":
            item.resume()
        else:
            item.complete()
        prescription.refresh_status()
        return (await self._prescription_dtos([await self.repo.save_prescription(prescription)]))[0]

    async def patient_medications(self, patient_id: uuid.UUID,
                                  status: Optional[ItemStatus] = None) -> list[PatientMedicationDTO]:
        """Medicamentos do paciente (itens de prescrições não canceladas), mais recentes primeiro."""
        if not await self.directory.get(patient_id):
            raise EntityNotFoundError("Paciente", patient_id)
        prescriptions, _ = await self.repo.search_prescriptions(PrescriptionFilters(patient_id=patient_id, limit=500))
        dtos = await self._prescription_dtos(prescriptions)
        return [PatientMedicationDTO(
            prescription_id=p.id, item_id=i.id, medication_name=i.medication_name, dose=i.dose, frequency=i.frequency,
            route=i.route, status=i.status, status_reason=i.status_reason, issued_at=p.issued_at,
            prescriber_name=p.prescriber_name, dispensed_quantity=i.dispensed_quantity, quantity=i.quantity,
        ) for p in dtos if p.status.value != "CANCELADA" for i in p.items if status is None or i.status == status]

    # ------------------------------------------------------------ dispensação

    async def dispense(self, dto: DispensationCreateDTO) -> DispensationDTO:
        now = self.clock()
        prescription = await self._get(dto.prescription_id)
        prescription.ensure_dispensable(now)
        await self._require_professional(dto.pharmacist_id, ProfessionalType.PHARMACIST, "dispensar")
        requested = {}
        for line in dto.items:
            if line.prescription_item_id in requested:
                raise BusinessRuleViolation("Cada item da prescrição deve aparecer uma única vez na dispensação.")
            requested[line.prescription_item_id] = line.quantity
        # Valida todos os itens antes de mexer no estoque (falha atômica para o usuário).
        for item_id, quantity in requested.items():
            item = prescription.item(item_id)
            if item.status != ItemStatus.IN_USE:
                raise BusinessRuleViolation("Somente itens em uso podem ser dispensados.")
            if quantity > item.remaining:
                raise BusinessRuleViolation(f"Quantidade acima do saldo da prescrição (restam {item.remaining:g}).")

        location = dto.location.strip().upper()
        dispensation = Dispensation(prescription_id=prescription.id, patient_id=prescription.patient_id,
                                    pharmacist_id=dto.pharmacist_id, location=location, dispensed_at=now,
                                    notes=dto.notes, id=uuid.uuid4())
        for item_id, quantity in requested.items():
            item = prescription.item(item_id)
            plan = await self.stock.withdraw(item.medication_id, location, quantity, now, MovementType.DISPENSATION,
                                             reference_id=dispensation.id, reason="Dispensação de prescrição")
            item.register_dispensed(quantity)
            dispensation.lines += [DispensationLine(
                prescription_item_id=item.id, medication_id=item.medication_id, quantity=portion,
                lot_id=lot.id if lot else None, lot_number=lot.lot_number if lot else None) for lot, portion in plan]
        prescription.refresh_status()
        await self.repo.save_prescription(prescription)
        saved = await self.repo.save_dispensation(dispensation)
        dto_out = (await self._dispensation_dtos([saved]))[0]
        dto_out.prescription_status = prescription.status
        await self.events.publish(DomainEvent(
            event_type=EventType.MEDICATION_DISPENSED, occurred_at=now, entity_type="Dispensacao",
            entity_id=saved.id, patient_id=saved.patient_id, professional_id=saved.pharmacist_id,
            summary=f"Medicamentos dispensados por {dto_out.pharmacist_name}: "
                    + "; ".join(f"{l.medication_name} {l.quantity:g}" + (f" (lote {l.lot_number})" if l.lot_number else "")
                                for l in dto_out.lines) + ".",
            data={"prescription_id": saved.prescription_id, "location": saved.location}))
        return dto_out

    async def dispensations(self, prescription_id: Optional[uuid.UUID] = None, patient_id: Optional[uuid.UUID] = None,
                            limit: int = 50, offset: int = 0) -> Page[DispensationDTO]:
        items, total = await self.repo.list_dispensations(prescription_id, patient_id, limit, offset)
        return Page(items=await self._dispensation_dtos(items), total=total, limit=limit, offset=offset)

    # ------------------------------------------------------------------ apoio

    async def _check_allergies(self, dto: PrescriptionCreateDTO, medications: dict) -> None:
        allergies = [a for a in await self.records.list_allergies(dto.patient_id) if a.status == AllergyStatus.ACTIVE]
        conflicts = sorted({f"{medications[i.medication_id].name} × {a.substance}"
                            for i in dto.items for a in allergies if allergy_matches(a.substance, medications[i.medication_id])})
        if not conflicts:
            return
        reason = (dto.allergy_override_reason or "").strip()
        if len(reason) < MIN_OVERRIDE_REASON:
            raise ConflictError(
                "Alergia registrada para: " + "; ".join(conflicts) +
                f". Para prosseguir, informe uma justificativa (mínimo de {MIN_OVERRIDE_REASON} caracteres).")

    async def _require_professional(self, professional_id: uuid.UUID, kind: ProfessionalType, action: str) -> None:
        professional = await self.professional_repo.get_by_id(professional_id)
        if not professional:
            raise EntityNotFoundError("Profissional", professional_id)
        if professional.professional_type != kind or not professional.is_available_for_booking:
            label = "médicos" if kind == ProfessionalType.DOCTOR else "farmacêuticos"
            raise BusinessRuleViolation(f"Somente {label} ativos podem {action}.")

    async def _get(self, prescription_id: uuid.UUID) -> Prescription:
        prescription = await self.repo.get_prescription(prescription_id)
        if not prescription:
            raise EntityNotFoundError("Prescrição", prescription_id)
        return prescription

    async def _prescription_dtos(self, prescriptions: list[Prescription]) -> list[PrescriptionDTO]:
        now = self.clock()
        medications = await self.repo.medications_by_ids({i.medication_id for p in prescriptions for i in p.items})
        patients = await self.repo.patient_names({p.patient_id for p in prescriptions})
        professionals = await self.professional_repo.get_names({p.prescriber_id for p in prescriptions})
        return [PrescriptionDTO(
            id=p.id, patient_id=p.patient_id, patient_name=patients.get(p.patient_id), prescriber_id=p.prescriber_id,
            prescriber_name=professionals.get(p.prescriber_id), appointment_id=p.appointment_id, issued_at=p.issued_at,
            valid_until=p.valid_until, is_expired=p.is_expired(now), status=p.status, special_control=p.special_control,
            allergy_override_reason=p.allergy_override_reason, notes=p.notes, cancellation_reason=p.cancellation_reason,
            items=[PrescriptionItemDTO(
                id=i.id, medication_id=i.medication_id,
                medication_name=_label(medications.get(i.medication_id)), dose=i.dose, frequency=i.frequency,
                duration_days=i.duration_days, route=i.route, quantity=i.quantity, dispensed_quantity=i.dispensed_quantity,
                remaining_quantity=i.remaining, instructions=i.instructions, status=i.status, status_reason=i.status_reason,
            ) for i in p.items],
        ) for p in prescriptions]

    async def _dispensation_dtos(self, dispensations: list[Dispensation]) -> list[DispensationDTO]:
        medications = await self.repo.medications_by_ids({l.medication_id for d in dispensations for l in d.lines})
        pharmacists = await self.professional_repo.get_names({d.pharmacist_id for d in dispensations})
        return [DispensationDTO(
            id=d.id, prescription_id=d.prescription_id, patient_id=d.patient_id, pharmacist_id=d.pharmacist_id,
            pharmacist_name=pharmacists.get(d.pharmacist_id), location=d.location, dispensed_at=d.dispensed_at,
            notes=d.notes, lines=[DispensationLineDTO(
                prescription_item_id=l.prescription_item_id, medication_id=l.medication_id,
                medication_name=_label(medications.get(l.medication_id)), lot_id=l.lot_id, lot_number=l.lot_number,
                quantity=l.quantity) for l in d.lines],
        ) for d in dispensations]


def _label(medication: Optional[Medication]) -> Optional[str]:
    return f"{medication.name} {medication.dosage}" if medication else None
