from datetime import date, datetime, timedelta
import uuid

import pytest

from app.domain.entities.laboratory import (
    Analyte, ExamCategory, ExamRequest, ExamStatus as S, ExamType, SampleType,
)
from app.domain.entities.reference_range import ReferenceRange, ResultFlag as F
from app.domain.entities.vital_signs import BmiCategory, VitalMetric as M, VitalSigns, bmi_category
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

NOW = datetime(2026, 10, 6, 10, 0)
PID = uuid.uuid4()


# --------------------------------------------------------- faixas de referência

@pytest.mark.parametrize("value,flag", [
    (50, F.CRITICAL_LOW), (65, F.LOW), (70, F.NORMAL), (99, F.NORMAL), (150, F.HIGH), (301, F.CRITICAL_HIGH),
])
def test_reference_range_classification(value, flag):
    glucose = ReferenceRange("mg/dL", 10, 1000, 70, 99, 54, 300)
    assert glucose.classify(value) == flag


def test_reference_range_rejects_implausible_values_and_describes_itself():
    spo2 = ReferenceRange("%", 50, 100, 95, None, 90, None)
    with pytest.raises(BusinessRuleViolation):
        spo2.validate(101, "Saturação")
    assert spo2.describe() == "≥ 95 %"
    assert spo2.classify(100) == F.NORMAL  # sem limite superior


# ------------------------------------------------------------------ sinais vitais

def test_vital_signs_flags_and_bmi():
    vitals = VitalSigns(patient_id=PID, recorded_at=NOW, systolic=150, diastolic=95, heart_rate=72,
                        oxygen_saturation=88, weight_kg=80, height_cm=170)
    flags = vitals.flags()
    assert flags[M.SYSTOLIC] == F.HIGH
    assert flags[M.OXYGEN_SATURATION] == F.CRITICAL_LOW
    assert flags[M.HEART_RATE] == F.NORMAL
    assert M.WEIGHT not in flags  # peso não tem faixa de referência
    assert vitals.bmi() == 27.7 and flags[M.BMI] == F.HIGH
    assert bmi_category(27.7) == BmiCategory.OVERWEIGHT


def test_bmi_uses_last_known_height():
    vitals = VitalSigns(patient_id=PID, recorded_at=NOW, weight_kg=60)
    assert vitals.bmi() is None
    assert vitals.bmi(fallback_height_cm=160) == 23.4


@pytest.mark.parametrize("kwargs,message", [
    ({}, "ao menos uma medida"),
    ({"systolic": 120}, "sistólico e diastólico"),
    ({"systolic": 80, "diastolic": 90}, "maior que a diastólica"),
    ({"temperature": 50.0}, "fora dos limites"),
])
def test_invalid_vital_signs(kwargs, message):
    with pytest.raises(BusinessRuleViolation, match=message):
        VitalSigns(patient_id=PID, recorded_at=NOW, **kwargs)


def test_vital_signs_dates():
    vitals = VitalSigns(patient_id=PID, recorded_at=NOW + timedelta(minutes=1), heart_rate=80)
    with pytest.raises(BusinessRuleViolation, match="futuro"):
        vitals.validate_date(NOW, date(1990, 1, 1))
    with pytest.raises(BusinessRuleViolation, match="nascimento"):
        VitalSigns(patient_id=PID, recorded_at=datetime(1980, 1, 1), heart_rate=80).validate_date(NOW, date(1990, 1, 1))


# -------------------------------------------------------------------- laboratório

def lipid_panel() -> ExamType:
    return ExamType(code="LIPID", name="Perfil lipídico", category=ExamCategory.BIOCHEMISTRY,
                    sample_type=SampleType.BLOOD, turnaround_hours=24, analytes=[
                        Analyte("CT", "Colesterol total", ReferenceRange("mg/dL", 20, 1000, None, 189), 0),
                        Analyte("HDL", "HDL", ReferenceRange("mg/dL", 5, 200, 40, None), 0),
                    ])


def request() -> ExamRequest:
    exam = ExamRequest(patient_id=PID, exam_type_id=uuid.uuid4(), requested_at=NOW, id=uuid.uuid4())
    exam.register_creation()
    return exam


def test_full_laboratory_flow():
    exam = request()
    exam.schedule(NOW + timedelta(days=1), NOW)
    exam.schedule(NOW + timedelta(days=2), NOW)  # reagendamento
    exam.collect(NOW + timedelta(days=2))
    assert exam.sample_code.startswith("AM20261008-")
    exam.start_processing(NOW + timedelta(days=2, hours=1))
    exam.record_results(lipid_panel(), {"CT": 230.4, "HDL": 55}, NOW + timedelta(days=2, hours=3))
    assert [(r.analyte_code, r.value, r.flag) for r in exam.results] == [("CT", 230.0, F.HIGH), ("HDL", 55.0, F.NORMAL)]
    assert exam.results[0].reference_text == "≤ 189 mg/dL"
    assert exam.has_abnormal_results and not exam.has_critical_results

    validator = uuid.uuid4()
    exam.validate(validator, NOW + timedelta(days=3))
    exam.release(NOW + timedelta(days=3))
    assert exam.status == S.RELEASED and exam.validated_by == validator
    assert [h.to_status for h in exam.history] == [
        S.REQUESTED, S.SCHEDULED, S.SCHEDULED, S.COLLECTED, S.PROCESSING, S.RESULTED, S.VALIDATED, S.RELEASED]
    assert exam.allowed_transitions() == []


def test_return_for_correction_discards_results():
    exam = request()
    exam.collect(NOW)  # coleta imediata, sem agendamento
    exam.start_processing(NOW)
    exam.record_results(lipid_panel(), {"CT": 180, "HDL": 50}, NOW)
    exam.return_for_correction("Valor de HDL transcrito errado", NOW)
    assert exam.status == S.PROCESSING and exam.results == []
    assert "Devolvido" in exam.history[-1].note


@pytest.mark.parametrize("values,message", [
    ({"CT": 180}, "Faltam resultados"),
    ({"CT": 180, "HDL": 50, "LDL": 100}, "não pertencem"),
    ({"CT": 5000, "HDL": 50}, "fora dos limites"),
])
def test_invalid_results_keep_the_exam_in_processing(values, message):
    exam = request()
    exam.collect(NOW)
    exam.start_processing(NOW)
    with pytest.raises(BusinessRuleViolation, match=message):
        exam.record_results(lipid_panel(), values, NOW)
    assert exam.status == S.PROCESSING and exam.results == []


def test_incoherent_laboratory_transitions():
    exam = request()
    with pytest.raises(InvalidTransitionError):
        exam.start_processing(NOW)  # sem coleta
    with pytest.raises(InvalidTransitionError):
        exam.release(NOW)
    with pytest.raises(BusinessRuleViolation):
        exam.schedule(NOW - timedelta(hours=1), NOW)

    exam.collect(NOW)
    with pytest.raises(InvalidTransitionError):
        exam.cancel("Depois da coleta não", NOW)

    cancelled = request()
    cancelled.cancel("Solicitação duplicada", NOW)
    with pytest.raises(InvalidTransitionError):
        cancelled.collect(NOW)


def test_exam_type_requires_unique_analytes():
    with pytest.raises(BusinessRuleViolation):
        ExamType(code="X", name="Vazio", category=ExamCategory.BIOCHEMISTRY, sample_type=SampleType.BLOOD,
                 turnaround_hours=1)
    duplicated = Analyte("A", "A", ReferenceRange("u", 0, 1))
    with pytest.raises(BusinessRuleViolation):
        ExamType(code="Y", name="Duplicado", category=ExamCategory.BIOCHEMISTRY, sample_type=SampleType.BLOOD,
                 turnaround_hours=1, analytes=[duplicated, duplicated])
