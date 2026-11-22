import pytest
from pydantic import TypeAdapter, ValidationError

from prior_auth_agent.models import ICD10Code, icd10_matches, normalize_icd10

ICD10 = TypeAdapter(ICD10Code)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("E11.9", "E11.9"),
        ("e119", "E11.9"),
        (" m06.9 ", "M06.9"),
        ("I10", "I10"),
        ("E1165", "E11.65"),
    ],
)
def test_codes_are_normalized(raw: str, expected: str) -> None:
    assert ICD10.validate_python(raw) == expected


@pytest.mark.parametrize("raw", ["", "11.9", "E1", "E11.", "E11.12345", "EE1.9", "E11-9"])
def test_invalid_codes_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        ICD10.validate_python(raw)


def test_non_string_is_rejected() -> None:
    with pytest.raises(TypeError):
        normalize_icd10(119)


@pytest.mark.parametrize(
    ("code", "prefix", "expected"),
    [
        ("E11.65", "E11", True),
        ("E11.65", "E11.6", True),
        ("E11.65", "e11.65", True),
        ("E11.9", "E11.6", False),
        ("E10.9", "E11", False),
        ("M05.79", "M06", False),
    ],
)
def test_prefix_matching(code: str, prefix: str, expected: bool) -> None:
    assert icd10_matches(code, prefix) is expected
