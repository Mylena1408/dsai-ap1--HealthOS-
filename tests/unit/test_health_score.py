from datetime import date, datetime, timedelta

from app.domain.services.health_score import HealthScoreInputs, ScoreBand, compute_health_score

TODAY = date(2026, 10, 6)


def component(score, key):
    return next(c for c in score.components if c.key == key)


def test_well_followed_patient_scores_good():
    score = compute_health_score(HealthScoreInputs(
        completed_appointments=4, last_completed_appointment=datetime(2026, 9, 1), has_upcoming_appointment=True,
        exams_requested=3, exams_released=3, prescribed_quantity=60, dispensed_quantity=60,
        vitals_recent=4, latest_vitals_abnormal_ratio=0.0), TODAY)
    assert score.score == 100 and score.band == ScoreBand.GOOD
    assert "não substitui avaliação profissional" in score.disclaimer


def test_missing_data_is_not_applicable_instead_of_zero():
    score = compute_health_score(HealthScoreInputs(
        last_completed_appointment=datetime(2026, 8, 1), vitals_recent=3, latest_vitals_abnormal_ratio=0), TODAY)
    assert component(score, "consultas").score is None
    assert component(score, "exames").score is None
    assert component(score, "medicamentos").score is None
    assert score.score == 100  # média só dos componentes aplicáveis (monitoramento e acompanhamento)


def test_each_component_reacts_to_its_facts():
    score = compute_health_score(HealthScoreInputs(
        completed_appointments=1, no_show_appointments=3, exams_requested=4, exams_released=2, exams_overdue=1,
        critical_exam_results=1, prescribed_quantity=100, dispensed_quantity=25, vitals_recent=1,
        latest_vitals_abnormal_ratio=0.5, active_conditions=2,
        last_completed_appointment=datetime.combine(TODAY - timedelta(days=300), datetime.min.time())), TODAY)
    assert component(score, "consultas").score == 25
    assert component(score, "exames").score == 40  # 50% concluídos - 10 por atraso
    assert "crítico" in component(score, "exames").explanation
    assert component(score, "medicamentos").score == 25
    assert component(score, "monitoramento").score == 40  # 1/3*60 + 0.5*40
    follow_up = component(score, "acompanhamento")
    assert follow_up.score == 60 and "condição(ões) ativa(s) sem retorno" in follow_up.explanation
    assert score.score == 38 and score.band == ScoreBand.INSUFFICIENT


def test_upcoming_appointment_improves_follow_up_and_no_vitals_counts_as_zero():
    score = compute_health_score(HealthScoreInputs(has_upcoming_appointment=True), TODAY)
    assert component(score, "acompanhamento").score == 40
    assert component(score, "monitoramento").score == 0
    assert score.score == 20
