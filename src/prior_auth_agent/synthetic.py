"""Load the bundled synthetic charts, payer policies and requests.

Everything under `prior_auth_agent/data` is fictional: made-up patients identified only
by `SYN-xxxxx` IDs, and a fictional payer. Each request comes with a scenario that
records which policy criteria it is expected to miss, so later evals can check the
agent's reasoning against a known answer.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable

from pydantic import Field, TypeAdapter

from prior_auth_agent.models import AuthRequest, Chart, PayerPolicy
from prior_auth_agent.models.base import DomainModel

DATA_PACKAGE = "prior_auth_agent.data"


class Scenario(DomainModel):
    request_id: str = Field(min_length=1)
    expected_unmet: tuple[str, ...]
    summary: str = Field(min_length=1)


def _data() -> Traversable:
    return resources.files(DATA_PACKAGE)


def _json_files(folder: str) -> list[Traversable]:
    return sorted(
        (f for f in _data().joinpath(folder).iterdir() if f.name.endswith(".json")),
        key=lambda f: f.name,
    )


@cache
def _charts() -> dict[str, Chart]:
    charts = (
        Chart.model_validate_json(f.read_text(encoding="utf-8")) for f in _json_files("charts")
    )
    return {c.patient.id: c for c in charts}


@cache
def _policies() -> dict[str, PayerPolicy]:
    policies = (
        PayerPolicy.model_validate_json(f.read_text(encoding="utf-8"))
        for f in _json_files("policies")
    )
    return {p.id: p for p in policies}


@cache
def load_requests() -> tuple[AuthRequest, ...]:
    raw = _data().joinpath("requests.json").read_text(encoding="utf-8")
    return TypeAdapter(tuple[AuthRequest, ...]).validate_json(raw)


@cache
def load_scenarios() -> tuple[Scenario, ...]:
    raw = _data().joinpath("scenarios.json").read_text(encoding="utf-8")
    return TypeAdapter(tuple[Scenario, ...]).validate_json(raw)


def patient_ids() -> tuple[str, ...]:
    return tuple(_charts())


def policy_ids() -> tuple[str, ...]:
    return tuple(_policies())


def load_chart(patient_id: str) -> Chart:
    try:
        return _charts()[patient_id]
    except KeyError:
        raise KeyError(f"no synthetic chart for patient {patient_id!r}") from None


def load_policy(policy_id: str) -> PayerPolicy:
    try:
        return _policies()[policy_id]
    except KeyError:
        raise KeyError(f"no policy {policy_id!r}") from None


def load_request(request_id: str) -> AuthRequest:
    for request in load_requests():
        if request.id == request_id:
            return request
    raise KeyError(f"no request {request_id!r}")
