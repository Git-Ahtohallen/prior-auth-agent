"""ICD-10-CM diagnosis codes.

Codes are normalized to the dotted, upper-case form (`e119` -> `E11.9`) so that
comparisons and prefix matching are reliable. A three-character category such as
`E11` is also valid; policies use categories to cover every code beneath them.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

_ICD10 = re.compile(r"^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")


def normalize_icd10(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("ICD-10 code must be a string")
    code = value.strip().upper()
    if "." not in code and len(code) > 3:
        code = f"{code[:3]}.{code[3:]}"
    if not _ICD10.fullmatch(code):
        raise ValueError(f"not a valid ICD-10-CM code: {value!r}")
    return code


ICD10Code = Annotated[str, BeforeValidator(normalize_icd10)]


def icd10_matches(code: str, prefix: str) -> bool:
    """True if `code` is `prefix` or falls under it (`E11.65` is under `E11` and `E11.6`)."""
    return normalize_icd10(code).startswith(normalize_icd10(prefix))
