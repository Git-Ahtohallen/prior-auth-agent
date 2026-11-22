from datetime import date

import pytest
from pydantic import ValidationError

from prior_auth_agent.models import (
    AgeCriterion,
    DiagnosisCriterion,
    LabCriterion,
    PayerPolicy,
    StepTherapyCriterion,
    StopReason,
)


def _policy(criteria: list[dict[str, object]]) -> PayerPolicy:
    return PayerPolicy.model_validate(
        {
            "id": "P1",
            "payer": "Test Plan (fictional)",
            "title": "Test",
            "drug": "drug",
            "drug_class": "cls",
            "effective": "2025-01-01",
            "criteria": criteria,
        }
    )


def test_criteria_are_parsed_by_kind() -> None:
    policy = _policy(
        [
            {"kind": "diagnosis", "id": "dx", "description": "d", "any_of": ["e11"]},
            {"kind": "age", "id": "age", "description": "a", "min_age": 18},
            {
                "kind": "lab",
                "id": "a1c",
                "description": "l",
                "test": "hba1c",
                "op": ">=",
                "value": 7,
                "unit": "%",
                "within_days": 90,
            },
            {
                "kind": "step_therapy",
                "id": "st",
                "description": "s",
                "drug_classes": ["biguanide"],
                "min_days": 90,
            },
            {
                "kind": "specialist",
                "id": "sp",
                "description": "x",
                "specialties": ["endo"],
                "within_days": 365,
            },
        ]
    )
    dx, age, lab, step, _ = policy.criteria
    assert isinstance(dx, DiagnosisCriterion) and dx.any_of == ("E11",)
    assert isinstance(age, AgeCriterion)
    assert isinstance(lab, LabCriterion)
    assert isinstance(step, StepTherapyCriterion)
    assert step.failure_reasons == (StopReason.INEFFECTIVE,)
    assert step.intolerance_satisfies and step.contraindication_satisfies
    assert policy.criterion("st") is step
    with pytest.raises(KeyError):
        policy.criterion("missing")
    assert policy.effective == date(2025, 1, 1)


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [(">=", 7.0, True), (">", 7.0, False), ("<=", 7.0, True), ("<", 7.0, False), (">=", 6.9, True)],
)
def test_lab_comparison(op: str, value: float, expected: bool) -> None:
    lab = LabCriterion.model_validate(
        {
            "id": "l",
            "description": "l",
            "test": "hba1c",
            "op": op,
            "value": value,
            "unit": "%",
            "within_days": 30,
        }
    )
    assert lab.passes(7.0) is expected


@pytest.mark.parametrize(
    ("criteria", "message"),
    [
        ([], "at least 1"),
        ([{"kind": "unknown", "id": "x", "description": "x"}], "kind"),
        ([{"kind": "age", "id": "a", "description": "a"}], "min_age, max_age"),
        ([{"kind": "age", "id": "a", "description": "a", "min_age": 70, "max_age": 18}], "greater"),
        ([{"kind": "diagnosis", "id": "d", "description": "d", "any_of": []}], "at least 1"),
        ([{"kind": "diagnosis", "id": "d", "description": "d", "any_of": ["bad"]}], "ICD-10"),
        (
            [
                {
                    "kind": "lab",
                    "id": "l",
                    "description": "l",
                    "test": "x",
                    "op": "==",
                    "value": 1,
                    "unit": "u",
                    "within_days": 1,
                }
            ],
            "op",
        ),
        (
            [
                {"kind": "age", "id": "a", "description": "a", "min_age": 1},
                {"kind": "age", "id": "a", "description": "b", "max_age": 2},
            ],
            "unique",
        ),
    ],
)
def test_invalid_policies_are_rejected(criteria: list[dict[str, object]], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _policy(criteria)
