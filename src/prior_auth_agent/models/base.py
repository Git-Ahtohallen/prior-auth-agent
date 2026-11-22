"""Shared Pydantic base class for domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Immutable, strict-about-unknown-fields base for every domain model.

    Collections on these models are tuples so a loaded chart or policy cannot be
    changed by accident while the agent reasons over it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
