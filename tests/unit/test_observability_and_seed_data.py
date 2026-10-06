import random

from app.domain.entities.patient import Patient
from app.infrastructure.observability.metrics import MetricsRegistry
from app.infrastructure.seed.fake_data import fake_patient, generate_cpf, is_valid_cpf


def test_metrics_registry_aggregates_by_route():
    registry = MetricsRegistry()
    registry.record("GET", "/x", 200, 10.0)
    registry.record("GET", "/x", 500, 30.0)
    registry.record("POST", "/y", 201, 5.0)

    snapshot = registry.snapshot()
    assert snapshot["requests_total"] == 3
    assert snapshot["errors_total"] == 1
    assert snapshot["error_rate"] == round(1 / 3, 4)
    assert snapshot["routes"]["GET /x"] == {
        "count": 2, "errors": 1, "avg_ms": 20.0, "max_ms": 30.0, "status_codes": {"200": 1, "500": 1},
    }

    registry.reset()
    assert registry.snapshot()["requests_total"] == 0


def test_generated_cpfs_have_valid_check_digits():
    rng = random.Random(1)
    cpfs = [generate_cpf(rng) for _ in range(200)]
    assert all(is_valid_cpf(cpf) for cpf in cpfs)
    assert is_valid_cpf("11144477735")
    assert not is_valid_cpf("11144477736")
    assert not is_valid_cpf("99999999999")


def test_fake_patients_are_deterministic_and_valid_for_the_domain():
    first = [fake_patient(random.Random(42)) for _ in range(2)]
    assert first[0] == first[1]

    data = fake_patient(random.Random(7))
    assert data["email"].endswith("@example.com")
    Patient(full_name=data["full_name"], birth_date=data["birth_date"], cpf=data["cpf"], gender=data["gender"])
