"""A synthetic patient chart: the evidence a prior authorization request is judged on."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from prior_auth_agent.models.base import DomainModel
from prior_auth_agent.models.codes import ICD10Code, icd10_matches

PatientId = str
PATIENT_ID_PATTERN = r"^SYN-\d{5}$"


class Patient(DomainModel):
    id: PatientId = Field(pattern=PATIENT_ID_PATTERN)
    birth_date: date
    sex: Literal["female", "male", "other", "unknown"]

    def age_on(self, day: date) -> int:
        had_birthday = (day.month, day.day) >= (self.birth_date.month, self.birth_date.day)
        return day.year - self.birth_date.year - (0 if had_birthday else 1)


class Diagnosis(DomainModel):
    code: ICD10Code
    description: str = Field(min_length=1)
    onset: date
    resolved: date | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.resolved is not None and self.resolved < self.onset:
            raise ValueError(f"diagnosis {self.code}: resolved before onset")
        return self

    def active_on(self, day: date) -> bool:
        return self.onset <= day and (self.resolved is None or day < self.resolved)


class StopReason(StrEnum):
    """Why a medication was stopped. Step therapy rules depend on this."""

    INEFFECTIVE = "ineffective"
    ADVERSE_EFFECT = "adverse_effect"
    COMPLETED = "completed"
    COST = "cost"
    OTHER = "other"


class Medication(DomainModel):
    """One trial of one drug, from start to (optional) stop."""

    name: str = Field(min_length=1)
    drug_class: str = Field(min_length=1)
    dose: str = Field(min_length=1)
    start: date
    end: date | None = None
    stop_reason: StopReason | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError(f"medication {self.name}: ends before it starts")
        if self.stop_reason is not None and self.end is None:
            raise ValueError(f"medication {self.name}: stop_reason given but no end date")
        return self

    def active_on(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)

    def duration_days(self, as_of: date) -> int:
        """Days on the drug, counting both the start and the last day taken."""
        last = self.end if self.end is not None and self.end < as_of else as_of
        return max(0, (last - self.start).days + 1)


class LabResult(DomainModel):
    test: str = Field(min_length=1, description="Lower-case test key, e.g. 'hba1c' or 'egfr'")
    value: float
    unit: str
    collected: date


class Encounter(DomainModel):
    id: str = Field(min_length=1)
    day: date
    kind: Literal["office", "telehealth", "inpatient", "emergency"]
    specialty: str = Field(min_length=1)
    diagnosis_codes: tuple[ICD10Code, ...] = ()
    note: str = ""


class Contraindication(DomainModel):
    """A documented reason the patient must not take a drug class."""

    drug_class: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    documented: date


class Chart(DomainModel):
    patient: Patient
    diagnoses: tuple[Diagnosis, ...] = ()
    medications: tuple[Medication, ...] = ()
    labs: tuple[LabResult, ...] = ()
    encounters: tuple[Encounter, ...] = ()
    contraindications: tuple[Contraindication, ...] = ()

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        ids = [e.id for e in self.encounters]
        if len(ids) != len(set(ids)):
            raise ValueError("encounter ids must be unique")
        born = self.patient.birth_date
        dated: Iterable[tuple[str, date]] = [
            *((f"diagnosis {d.code}", d.onset) for d in self.diagnoses),
            *((f"medication {m.name}", m.start) for m in self.medications),
            *((f"lab {lab.test}", lab.collected) for lab in self.labs),
            *((f"encounter {e.id}", e.day) for e in self.encounters),
        ]
        for label, day in dated:
            if day < born:
                raise ValueError(f"{label} is dated before the patient's birth")
        return self

    def active_diagnoses(self, as_of: date) -> tuple[Diagnosis, ...]:
        return tuple(d for d in self.diagnoses if d.active_on(as_of))

    def has_diagnosis(self, prefixes: Iterable[str], as_of: date) -> bool:
        wanted = tuple(prefixes)
        return any(icd10_matches(d.code, p) for d in self.active_diagnoses(as_of) for p in wanted)

    def medications_in_class(self, drug_class: str) -> tuple[Medication, ...]:
        return tuple(m for m in self.medications if m.drug_class == drug_class)

    def contraindicated(self, drug_class: str, as_of: date) -> Contraindication | None:
        return next(
            (
                c
                for c in self.contraindications
                if c.drug_class == drug_class and c.documented <= as_of
            ),
            None,
        )

    def latest_lab(self, test: str, as_of: date) -> LabResult | None:
        results = [lab for lab in self.labs if lab.test == test and lab.collected <= as_of]
        return max(results, key=lambda lab: lab.collected, default=None)

    def encounters_with(self, specialties: Iterable[str], since: date) -> tuple[Encounter, ...]:
        wanted = set(specialties)
        return tuple(e for e in self.encounters if e.specialty in wanted and e.day >= since)
