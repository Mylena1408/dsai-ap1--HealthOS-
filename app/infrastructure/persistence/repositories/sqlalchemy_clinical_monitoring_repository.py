import uuid

from sqlalchemy import desc, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.clinical_monitoring_repository import (
    ExamRequestFilters, ExamRequestNames, LaboratoryRepository, VitalSignsRepository,
)
from app.domain.entities.laboratory import (
    Analyte, ExamCategory, ExamPriority, ExamRequest, ExamResult, ExamStatus, ExamStatusChange, ExamType,
    Laboratory, SampleType,
)
from app.domain.entities.reference_range import ReferenceRange, ResultFlag
from app.domain.entities.vital_signs import VitalMetric, VitalSigns
from app.infrastructure.persistence.models.clinical_monitoring_model import (
    AnalyteModel, ExamRequestModel, ExamResultModel, ExamStatusHistoryModel, ExamTypeModel, LaboratoryModel,
    VitalSignsModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel

_VITAL_FIELDS = [m.value for m in VitalMetric if m != VitalMetric.BMI] + ["professional_id", "notes", "recorded_at"]


class SQLAlchemyVitalSignsRepository(VitalSignsRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, vitals: VitalSigns) -> VitalSigns:
        model = await self.session.get(VitalSignsModel, vitals.id) if vitals.id else None
        if model is None:
            model = VitalSignsModel(id=vitals.id or uuid.uuid4(), patient_id=vitals.patient_id)
            self.session.add(model)
        for name in _VITAL_FIELDS:
            setattr(model, name, getattr(vitals, name))
        await self.session.flush()
        vitals.id = model.id
        return vitals

    async def page(self, patient_id, date_from, date_to, limit, offset):
        conditions = [VitalSignsModel.patient_id == patient_id]
        if date_from:
            conditions.append(VitalSignsModel.recorded_at >= date_from)
        if date_to:
            conditions.append(VitalSignsModel.recorded_at <= date_to)
        total = await self.session.scalar(select(func.count()).select_from(VitalSignsModel).where(*conditions))
        rows = await self.session.scalars(select(VitalSignsModel).where(*conditions)
                                          .order_by(desc(VitalSignsModel.recorded_at)).limit(limit).offset(offset))
        return [self._to_domain(m) for m in rows], total

    async def history(self, patient_id, limit):
        rows = await self.session.scalars(select(VitalSignsModel).where(VitalSignsModel.patient_id == patient_id)
                                          .order_by(desc(VitalSignsModel.recorded_at)).limit(limit))
        return list(reversed([self._to_domain(m) for m in rows]))

    async def last_height(self, patient_id, until):
        return await self.session.scalar(
            select(VitalSignsModel.height_cm)
            .where(VitalSignsModel.patient_id == patient_id, VitalSignsModel.height_cm.is_not(None),
                   VitalSignsModel.recorded_at <= until)
            .order_by(desc(VitalSignsModel.recorded_at)).limit(1))

    async def height_history(self, patient_id):
        rows = await self.session.execute(
            select(VitalSignsModel.recorded_at, VitalSignsModel.height_cm)
            .where(VitalSignsModel.patient_id == patient_id, VitalSignsModel.height_cm.is_not(None))
            .order_by(VitalSignsModel.recorded_at))
        return [tuple(row) for row in rows.all()]

    @staticmethod
    def _to_domain(m: VitalSignsModel) -> VitalSigns:
        return VitalSigns(id=m.id, patient_id=m.patient_id, **{name: getattr(m, name) for name in _VITAL_FIELDS})


class SQLAlchemyLaboratoryRepository(LaboratoryRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    # --------------------------------------------------------------- catálogo

    async def list_exam_types(self):
        rows = await self.session.scalars(select(ExamTypeModel).order_by(ExamTypeModel.name))
        return [self._exam_type(m) for m in rows]

    async def get_exam_type(self, exam_type_id):
        model = await self.session.get(ExamTypeModel, exam_type_id)
        return self._exam_type(model) if model else None

    async def get_exam_type_by_code(self, code):
        model = await self.session.scalar(select(ExamTypeModel).where(ExamTypeModel.code == code))
        return self._exam_type(model) if model else None

    async def save_exam_type(self, exam_type: ExamType) -> ExamType:
        model = await self.session.get(ExamTypeModel, exam_type.id) if exam_type.id else None
        if model is None:
            model = ExamTypeModel(id=exam_type.id or uuid.uuid4(), analytes=[])
            self.session.add(model)
        model.code, model.name = exam_type.code, exam_type.name
        model.category, model.sample_type = exam_type.category.value, exam_type.sample_type.value
        model.turnaround_hours, model.preparation = exam_type.turnaround_hours, exam_type.preparation
        model.analytes = [AnalyteModel(
            position=i, code=a.code, name=a.name, unit=a.reference.unit, decimals=a.decimals,
            plausible_min=a.reference.plausible_min, plausible_max=a.reference.plausible_max,
            normal_min=a.reference.normal_min, normal_max=a.reference.normal_max,
            critical_min=a.reference.critical_min, critical_max=a.reference.critical_max,
        ) for i, a in enumerate(exam_type.analytes)]
        await self.session.flush()
        exam_type.id = model.id
        return exam_type

    async def list_laboratories(self):
        rows = await self.session.scalars(select(LaboratoryModel).order_by(LaboratoryModel.name))
        return [Laboratory(id=m.id, name=m.name, address=m.address) for m in rows]

    async def get_laboratory(self, laboratory_id):
        m = await self.session.get(LaboratoryModel, laboratory_id)
        return Laboratory(id=m.id, name=m.name, address=m.address) if m else None

    async def save_laboratory(self, laboratory: Laboratory) -> Laboratory:
        model = await self.session.get(LaboratoryModel, laboratory.id) if laboratory.id else None
        if model is None:
            model = LaboratoryModel(id=laboratory.id or uuid.uuid4())
            self.session.add(model)
        model.name, model.address = laboratory.name, laboratory.address
        await self.session.flush()
        laboratory.id = model.id
        return laboratory

    # ------------------------------------------------------------ solicitações

    async def save_request(self, request: ExamRequest) -> ExamRequest:
        model = await self.session.get(ExamRequestModel, request.id) if request.id else None
        if model is None:
            model = ExamRequestModel(id=request.id or uuid.uuid4(), results=[], history=[])
            self.session.add(model)
        request.id = model.id
        for name in ("patient_id", "exam_type_id", "requested_by", "appointment_id", "laboratory_id",
                     "clinical_indication", "requested_at", "scheduled_for", "sample_code", "collected_at",
                     "result_notes", "resulted_at", "validated_by", "validated_at", "released_at",
                     "cancellation_reason"):
            setattr(model, name, getattr(request, name))
        model.priority, model.status = request.priority.value, request.status.value
        # Os resultados atuais substituem os anteriores (ex.: após devolução para correção).
        model.results = [ExamResultModel(
            position=i, analyte_code=r.analyte_code, analyte_name=r.analyte_name, value=r.value, unit=r.unit,
            reference_text=r.reference_text, flag=r.flag.value,
        ) for i, r in enumerate(request.results)]
        for change in request.history:
            if change.id is None:
                change.id = uuid.uuid4()
                model.history.append(ExamStatusHistoryModel(
                    id=change.id, from_status=change.from_status.value if change.from_status else None,
                    to_status=change.to_status.value, changed_at=change.changed_at, note=change.note))
        await self.session.flush()
        return request

    async def get_request(self, request_id):
        model = await self.session.get(ExamRequestModel, request_id)
        return self._request(model) if model else None

    async def search_requests(self, filters: ExamRequestFilters):
        conditions = []
        if filters.patient_id:
            conditions.append(ExamRequestModel.patient_id == filters.patient_id)
        if filters.statuses:
            conditions.append(ExamRequestModel.status.in_([s.value for s in filters.statuses]))
        if filters.exam_type_id:
            conditions.append(ExamRequestModel.exam_type_id == filters.exam_type_id)
        if filters.requested_by:
            conditions.append(ExamRequestModel.requested_by == filters.requested_by)
        if filters.priority:
            conditions.append(ExamRequestModel.priority == filters.priority.value)
        if filters.date_from:
            conditions.append(ExamRequestModel.requested_at >= filters.date_from)
        if filters.date_to:
            conditions.append(ExamRequestModel.requested_at <= filters.date_to)
        if filters.only_abnormal:
            conditions.append(exists().where(ExamResultModel.exam_request_id == ExamRequestModel.id,
                                             ExamResultModel.flag != ResultFlag.NORMAL.value))
        total = await self.session.scalar(select(func.count()).select_from(ExamRequestModel).where(*conditions))
        order = desc(ExamRequestModel.requested_at) if filters.newest_first else ExamRequestModel.requested_at
        rows = await self.session.scalars(select(ExamRequestModel).where(*conditions)
                                          .order_by(order).limit(filters.limit).offset(filters.offset))
        return [self._request(m) for m in rows], total

    async def names_for(self, requests: list[ExamRequest]) -> ExamRequestNames:
        patient_ids = {r.patient_id for r in requests}
        professional_ids = {pid for r in requests for pid in (r.requested_by, r.validated_by) if pid}
        type_ids = {r.exam_type_id for r in requests}
        lab_ids = {r.laboratory_id for r in requests if r.laboratory_id}
        names = ExamRequestNames()
        if patient_ids:
            names.patients = dict((await self.session.execute(
                select(PatientModel.id, PatientModel.full_name).where(PatientModel.id.in_(patient_ids)))).all())
        if professional_ids:
            names.professionals = dict((await self.session.execute(
                select(ProfessionalModel.id, ProfessionalModel.full_name)
                .where(ProfessionalModel.id.in_(professional_ids)))).all())
        if type_ids:
            names.exam_types = {m.id: self._exam_type(m) for m in await self.session.scalars(
                select(ExamTypeModel).where(ExamTypeModel.id.in_(type_ids)))}
        if lab_ids:
            names.laboratories = dict((await self.session.execute(
                select(LaboratoryModel.id, LaboratoryModel.name).where(LaboratoryModel.id.in_(lab_ids)))).all())
        return names

    async def released_results(self, patient_id, analyte_code):
        rows = await self.session.execute(
            select(ExamRequestModel.collected_at, ExamResultModel)
            .join(ExamResultModel, ExamResultModel.exam_request_id == ExamRequestModel.id)
            .where(ExamRequestModel.patient_id == patient_id, ExamRequestModel.status == ExamStatus.RELEASED.value,
                   ExamResultModel.analyte_code == analyte_code)
            .order_by(ExamRequestModel.collected_at))
        return [(collected_at, self._result(r)) for collected_at, r in rows.all()]

    # -------------------------------------------------------------- mapeamento

    @staticmethod
    def _exam_type(m: ExamTypeModel) -> ExamType:
        return ExamType(
            id=m.id, code=m.code, name=m.name, category=ExamCategory(m.category),
            sample_type=SampleType(m.sample_type), turnaround_hours=m.turnaround_hours, preparation=m.preparation,
            analytes=[Analyte(id=a.id, code=a.code, name=a.name, decimals=a.decimals, reference=ReferenceRange(
                unit=a.unit, plausible_min=a.plausible_min, plausible_max=a.plausible_max,
                normal_min=a.normal_min, normal_max=a.normal_max,
                critical_min=a.critical_min, critical_max=a.critical_max)) for a in m.analytes],
        )

    @staticmethod
    def _result(r: ExamResultModel) -> ExamResult:
        return ExamResult(analyte_code=r.analyte_code, analyte_name=r.analyte_name, value=r.value, unit=r.unit,
                          reference_text=r.reference_text, flag=ResultFlag(r.flag))

    def _request(self, m: ExamRequestModel) -> ExamRequest:
        return ExamRequest(
            id=m.id, patient_id=m.patient_id, exam_type_id=m.exam_type_id, requested_at=m.requested_at,
            requested_by=m.requested_by, appointment_id=m.appointment_id, laboratory_id=m.laboratory_id,
            priority=ExamPriority(m.priority), clinical_indication=m.clinical_indication,
            status=ExamStatus(m.status), scheduled_for=m.scheduled_for, sample_code=m.sample_code,
            collected_at=m.collected_at, results=[self._result(r) for r in m.results], result_notes=m.result_notes,
            resulted_at=m.resulted_at, validated_by=m.validated_by, validated_at=m.validated_at,
            released_at=m.released_at, cancellation_reason=m.cancellation_reason,
            history=[ExamStatusChange(
                id=h.id, from_status=ExamStatus(h.from_status) if h.from_status else None,
                to_status=ExamStatus(h.to_status), changed_at=h.changed_at, note=h.note) for h in m.history],
        )
