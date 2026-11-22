"""Payer coverage policies and the prior authorization request they are applied to.

A policy is a list of typed criteria. Every criterion has a stable `id` so a draft
letter (and the human reviewer) can say exactly which requirement each piece of chart
evidence satisfies.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from prior_auth_agent.models.base import DomainModel
from prior_auth_agent.models.chart import PATIENT_ID_PATTERN, StopReason
from prior_auth_agent.models.codes import ICD10Code

_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
}


class _Criterion(DomainModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class DiagnosisCriterion(_Criterion):
    """The patient has an active diagnosis under one of these ICD-10 codes or categories."""

    kind: Literal["diagnosis"] = "diagnosis"
    any_of: tuple[ICD10Code, ...] = Field(min_length=1)


class AgeCriterion(_Criterion):
    kind: Literal["age"] = "age"
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.min_age is None and self.max_age is None:
            raise ValueError(f"criterion {self.id}: set min_age, max_age or both")
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError(f"criterion {self.id}: min_age is greater than max_age")
        return self


class LabCriterion(_Criterion):
    """The most recent result for `test`, taken within `within_days`, satisfies `op value`."""

    kind: Literal["lab"] = "lab"
    test: str = Field(min_length=1)
    op: Literal[">=", ">", "<=", "<"]
    value: float
    unit: str
    within_days: int = Field(gt=0)

    def passes(self, result_value: float) -> bool:
        return _OPERATORS[self.op](result_value, self.value)


class StepTherapyCriterion(_Criterion):
    """The patient tried and failed a preferred drug class first.

    A trial counts if it lasted at least `min_days` and was stopped as ineffective
    (or is still running without control). Stopping for an adverse effect counts at
    any duration when `intolerance_satisfies` is set, and a documented
    contraindication counts when `contraindication_satisfies` is set. That mirrors the
    usual "trial of at least N days, or intolerance, or contraindication" wording.
    """

    kind: Literal["step_therapy"] = "step_therapy"
    drug_classes: tuple[str, ...] = Field(min_length=1)
    min_days: int = Field(gt=0)
    failure_reasons: tuple[StopReason, ...] = (StopReason.INEFFECTIVE,)
    intolerance_satisfies: bool = True
    contraindication_satisfies: bool = True


class SpecialistCriterion(_Criterion):
    """Prescribed by or in consultation with one of these specialties, recently."""

    kind: Literal["specialist"] = "specialist"
    specialties: tuple[str, ...] = Field(min_length=1)
    within_days: int = Field(gt=0)


Criterion = Annotated[
    DiagnosisCriterion | AgeCriterion | LabCriterion | StepTherapyCriterion | SpecialistCriterion,
    Field(discriminator="kind"),
]


class PayerPolicy(DomainModel):
    id: str = Field(min_length=1)
    payer: str = Field(min_length=1)
    title: str = Field(min_length=1)
    drug: str = Field(min_length=1)
    drug_class: str = Field(min_length=1)
    effective: date
    criteria: tuple[Criterion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_criterion_ids(self) -> Self:
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError(f"policy {self.id}: criterion ids must be unique")
        return self

    def criterion(self, criterion_id: str) -> Criterion:
        for c in self.criteria:
            if c.id == criterion_id:
                return c
        raise KeyError(criterion_id)


class AuthRequest(DomainModel):
    """A clinician's request to cover one drug for one patient under one policy."""

    id: str = Field(min_length=1)
    patient_id: str = Field(pattern=PATIENT_ID_PATTERN)
    policy_id: str = Field(min_length=1)
    drug: str = Field(min_length=1)
    dose: str = Field(min_length=1)
    diagnosis_code: ICD10Code
    requested_on: date
    prescriber_specialty: str = Field(min_length=1)
