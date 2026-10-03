from typing import List, Optional
import uuid
from app.application.interfaces.patient_repository import PatientRepository
from app.application.dtos.patient_dto import PatientCreateDTO, PatientUpdateDTO, PatientResponseDTO
from app.domain.entities.patient import Patient
from app.domain.exceptions.base import DomainException

class ManagePatientUseCase:
    """
    Caso de Uso para a gestão de pacientes.
    Orquestra a criação, busca e atualização de dados cadastrais.
    """

    def __init__(self, patient_repository: PatientRepository):
        self.patient_repository = patient_repository

    async def create_patient(self, request: PatientCreateDTO) -> PatientResponseDTO:
        # 1. Validação de Unicidade: CPF já cadastrado?
        existing_patient = await self.patient_repository.get_by_cpf(request.cpf)
        if existing_patient:
            raise DomainException(f"Paciente com CPF {request.cpf} já cadastrado.")

        # 2. Criação da Entidade de Domínio
        try:
            patient = Patient(
                full_name=request.full_name,
                birth_date=request.birth_date,
                cpf=request.cpf,
                gender=request.gender,
                insurance_provider=request.insurance_provider,
                insurance_number=request.insurance_number,
                phone=request.phone,
                email=request.email,
                address=request.address
            )
        except ValueError as exc:
            raise DomainException(str(exc)) from exc

        # 3. Persistência
        created_patient = await self.patient_repository.save(patient)

        # 4. Retorno via DTO
        return PatientResponseDTO(
            id=created_patient.id,
            full_name=created_patient.full_name,
            birth_date=created_patient.birth_date,
            cpf=created_patient.cpf,
            gender=created_patient.gender,
            insurance_provider=created_patient.insurance_provider,
            insurance_number=created_patient.insurance_number,
            phone=created_patient.phone,
            email=created_patient.email,
            address=created_patient.address
        )

    async def list_patients(self, skip: int, limit: int) -> List[PatientResponseDTO]:
        patients = await self.patient_repository.list_all(skip=skip, limit=limit)
        return [
            PatientResponseDTO(
                id=p.id,
                full_name=p.full_name,
                birth_date=p.birth_date,
                cpf=p.cpf,
                gender=p.gender,
                insurance_provider=p.insurance_provider,
                insurance_number=p.insurance_number,
                phone=p.phone,
                email=p.email,
                address=p.address
            ) for p in patients
        ]

    async def get_patient_by_id(self, patient_id: uuid.UUID) -> PatientResponseDTO:
        patient = await self.patient_repository.get_by_id(patient_id)
        if not patient:
            raise DomainException(f"Paciente com ID {patient_id} não encontrado.")

        return PatientResponseDTO(
            id=patient.id,
            full_name=patient.full_name,
            birth_date=patient.birth_date,
            cpf=patient.cpf,
            gender=patient.gender,
            insurance_provider=patient.insurance_provider,
            insurance_number=patient.insurance_number,
            phone=patient.phone,
            email=patient.email,
            address=patient.address
        )

    async def update_patient(self, patient_id: uuid.UUID, request: PatientUpdateDTO) -> PatientResponseDTO:
        patient = await self.patient_repository.get_by_id(patient_id)
        if not patient:
            raise DomainException(f"Paciente com ID {patient_id} não encontrado.")

        # Atualiza apenas os campos fornecidos
        if request.full_name: patient.full_name = request.full_name
        if request.phone: patient.phone = request.phone
        if request.email: patient.email = request.email
        if request.address: patient.address = request.address
        if request.insurance_provider: patient.insurance_provider = request.insurance_provider
        if request.insurance_number is not None: patient.insurance_number = request.insurance_number

        updated_patient = await self.patient_repository.update(patient)

        return PatientResponseDTO(
            id=updated_patient.id,
            full_name=updated_patient.full_name,
            birth_date=updated_patient.birth_date,
            cpf=updated_patient.cpf,
            gender=updated_patient.gender,
            insurance_provider=updated_patient.insurance_provider,
            insurance_number=updated_patient.insurance_number,
            phone=updated_patient.phone,
            email=updated_patient.email,
            address=updated_patient.address
        )
