from datetime import date

import pytest
from pydantic import ValidationError

from prior_auth_agent.models import Chart, Diagnosis, Medication, Patient, StopReason

PATIENT = Patient(id="SYN-00001", birth_date=date(1980, 6, 15), sex="female")


def test_age_counts_birthday() -> None:
    assert PATIENT.age_on(date(2025, 6, 14)) == 44
    assert PATIENT.age_on(date(2025, 6, 15)) == 45


def test_patient_id_must_be_synthetic() -> None:
    with pytest.raises(ValidationError):
        Patient(id="123-45-6789", birth_date=date(1980, 1, 1), sex="male")


def test_models_are_frozen_and_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PATIENT.sex = "male"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Patient.model_validate(
            {"id": "SYN-00002", "birth_date": "1990-01-01", "sex": "male", "ssn": "x"}
        )


def test_diagnosis_active_window() -> None:
    dx = Diagnosis(
        code="j06.9", description="URI", onset=date(2025, 1, 1), resolved=date(2025, 1, 10)
    )
    assert dx.code == "J06.9"
    assert dx.active_on(date(2025, 1, 5))
    assert not dx.active_on(date(2025, 1, 10))
    assert not dx.active_on(date(2024, 12, 31))
    with pytest.raises(ValidationError, match="resolved before onset"):
        Diagnosis(
            code="J06.9", description="URI", onset=date(2025, 1, 10), resolved=date(2025, 1, 1)
        )


def _metformin(**kwargs: object) -> Medication:
    fields: dict[str, object] = {
        "name": "metformin",
        "drug_class": "biguanide",
        "dose": "500 mg",
        "start": date(2025, 1, 1),
        **kwargs,
    }
    return Medication.model_validate(fields)


def test_medication_duration_is_inclusive_and_capped() -> None:
    stopped = _metformin(end=date(2025, 3, 31), stop_reason="ineffective")
    assert stopped.stop_reason is StopReason.INEFFECTIVE
    assert stopped.duration_days(date(2025, 12, 31)) == 90
    assert stopped.duration_days(date(2025, 1, 10)) == 10
    ongoing = _metformin()
    assert ongoing.duration_days(date(2025, 1, 1)) == 1
    assert ongoing.duration_days(date(2024, 12, 1)) == 0
    assert ongoing.active_on(date(2026, 1, 1))


def test_medication_date_rules() -> None:
    with pytest.raises(ValidationError, match="ends before it starts"):
        _metformin(end=date(2024, 12, 1))
    with pytest.raises(ValidationError, match="no end date"):
        _metformin(stop_reason="ineffective")


def test_chart_rejects_events_before_birth_and_duplicate_encounters() -> None:
    with pytest.raises(ValidationError, match="before the patient's birth"):
        Chart(
            patient=PATIENT,
            diagnoses=(Diagnosis(code="I10", description="HTN", onset=date(1970, 1, 1)),),
        )
    enc = {"id": "e1", "day": "2025-01-01", "kind": "office", "specialty": "primary_care"}
    with pytest.raises(ValidationError, match="unique"):
        Chart.model_validate({"patient": PATIENT.model_dump(), "encounters": [enc, enc]})


def test_chart_queries() -> None:
    chart = Chart.model_validate(
        {
            "patient": PATIENT.model_dump(),
            "diagnoses": [
                {"code": "E11.65", "description": "T2DM", "onset": "2020-01-01"},
                {
                    "code": "J06.9",
                    "description": "URI",
                    "onset": "2024-01-01",
                    "resolved": "2024-01-15",
                },
            ],
            "medications": [
                {
                    "name": "metformin",
                    "drug_class": "biguanide",
                    "dose": "1 g",
                    "start": "2020-01-01",
                }
            ],
            "labs": [
                {"test": "hba1c", "value": 8.0, "unit": "%", "collected": "2025-01-01"},
                {"test": "hba1c", "value": 7.2, "unit": "%", "collected": "2025-06-01"},
            ],
            "encounters": [
                {"id": "e1", "day": "2025-06-01", "kind": "office", "specialty": "endocrinology"}
            ],
            "contraindications": [
                {"drug_class": "sulfonylurea", "reason": "hypoglycemia", "documented": "2023-05-01"}
            ],
        }
    )
    day = date(2025, 7, 1)
    assert chart.has_diagnosis(["E11"], day)
    assert not chart.has_diagnosis(["J06"], day)
    assert [m.name for m in chart.medications_in_class("biguanide")] == ["metformin"]
    latest = chart.latest_lab("hba1c", day)
    assert latest is not None and latest.value == 7.2
    early = chart.latest_lab("hba1c", date(2025, 3, 1))
    assert early is not None and early.value == 8.0
    assert chart.latest_lab("egfr", day) is None
    assert chart.contraindicated("sulfonylurea", day) is not None
    assert chart.contraindicated("sulfonylurea", date(2023, 1, 1)) is None
    assert len(chart.encounters_with(["endocrinology"], since=date(2025, 1, 1))) == 1
    assert chart.encounters_with(["rheumatology"], since=date(2020, 1, 1)) == ()
