from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.search_queries import SearchHit, SearchQueries
from app.infrastructure.persistence.models.billing_model import InvoiceModel
from app.infrastructure.persistence.models.clinical_monitoring_model import ExamRequestModel, ExamTypeModel
from app.infrastructure.persistence.models.medication_model import MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel

ESCAPE = "\\"


def contains(text: str) -> str:
    """Padrão LIKE de "contém", com % e _ digitados tratados como caracteres comuns."""
    escaped = text.replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")
    return f"%{escaped}%"


class SQLAlchemySearchQueries(SearchQueries):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _run(self, stmt, condition, order, limit):
        total = await self.session.scalar(select(func.count()).select_from(stmt.where(condition).subquery()))
        rows = (await self.session.execute(stmt.where(condition).order_by(order).limit(limit))).all()
        return rows, total

    async def patients(self, text: str, digits: Optional[str], limit: int):
        clauses = [PatientModel.full_name.ilike(contains(text), escape=ESCAPE)]
        if digits:
            clauses.append(PatientModel.cpf.like(contains(digits), escape=ESCAPE))
        rows, total = await self._run(select(PatientModel.id, PatientModel.full_name, PatientModel.cpf,
                                             PatientModel.birth_date), or_(*clauses), PatientModel.full_name, limit)
        return [SearchHit(r.id, r.full_name, {"cpf": r.cpf, "birth_date": r.birth_date}) for r in rows], total

    async def professionals(self, text: str, limit: int):
        pattern = contains(text)
        rows, total = await self._run(
            select(ProfessionalModel.id, ProfessionalModel.full_name, ProfessionalModel.professional_type,
                   ProfessionalModel.registry_number),
            or_(ProfessionalModel.full_name.ilike(pattern, escape=ESCAPE),
                ProfessionalModel.registry_number.ilike(pattern, escape=ESCAPE)),
            ProfessionalModel.full_name, limit)
        return [SearchHit(r.id, r.full_name, {"type": r.professional_type, "registry": r.registry_number})
                for r in rows], total

    async def medications(self, text: str, limit: int):
        pattern = contains(text)
        rows, total = await self._run(
            select(MedicationModel.id, MedicationModel.name, MedicationModel.generic_name, MedicationModel.dosage),
            or_(MedicationModel.name.ilike(pattern, escape=ESCAPE),
                MedicationModel.generic_name.ilike(pattern, escape=ESCAPE)),
            MedicationModel.name, limit)
        return [SearchHit(r.id, r.name, {"generic": r.generic_name, "dosage": r.dosage}) for r in rows], total

    async def exams(self, text: str, limit: int):
        rows, total = await self._run(
            select(ExamRequestModel.id, ExamRequestModel.sample_code, ExamRequestModel.status,
                   ExamRequestModel.patient_id, ExamTypeModel.name, PatientModel.full_name)
            .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            .join(PatientModel, PatientModel.id == ExamRequestModel.patient_id),
            ExamRequestModel.sample_code.ilike(contains(text), escape=ESCAPE),
            ExamRequestModel.sample_code, limit)
        return [SearchHit(r.id, f"{r.sample_code} · {r.name}",
                          {"status": r.status, "patient_id": r.patient_id, "patient": r.full_name}) for r in rows], total

    async def invoices(self, text: str, limit: int):
        rows, total = await self._run(
            select(InvoiceModel.id, InvoiceModel.invoice_number, InvoiceModel.status, PatientModel.full_name)
            .join(PatientModel, PatientModel.id == InvoiceModel.patient_id),
            InvoiceModel.invoice_number.ilike(contains(text), escape=ESCAPE),
            InvoiceModel.invoice_number.desc(), limit)
        return [SearchHit(r.id, r.invoice_number, {"status": r.status, "patient": r.full_name}) for r in rows], total
