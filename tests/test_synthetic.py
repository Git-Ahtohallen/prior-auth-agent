import pytest

from prior_auth_agent import synthetic
from prior_auth_agent.models import icd10_matches


def test_all_fixtures_load() -> None:
    assert len(synthetic.patient_ids()) == 5
    assert set(synthetic.policy_ids()) == {"SHP-RX-GLP1-001", "SHP-RX-TNF-001"}
    assert len(synthetic.load_requests()) == 5


def test_payer_is_marked_fictional() -> None:
    for pid in synthetic.policy_ids():
        assert "fictional" in synthetic.load_policy(pid).payer


def test_requests_reference_existing_charts_policies_and_diagnoses() -> None:
    for req in synthetic.load_requests():
        chart = synthetic.load_chart(req.patient_id)
        policy = synthetic.load_policy(req.policy_id)
        assert req.drug == policy.drug
        assert any(d.code == req.diagnosis_code for d in chart.diagnoses)
        dx = next(c for c in policy.criteria if c.kind == "diagnosis")
        assert any(icd10_matches(req.diagnosis_code, p) for p in dx.any_of)


def test_every_request_has_a_scenario_with_real_criterion_ids() -> None:
    scenarios = {s.request_id: s for s in synthetic.load_scenarios()}
    assert set(scenarios) == {r.id for r in synthetic.load_requests()}
    for req in synthetic.load_requests():
        policy = synthetic.load_policy(req.policy_id)
        for criterion_id in scenarios[req.id].expected_unmet:
            policy.criterion(criterion_id)  # raises if the id is wrong


def test_scenarios_cover_both_outcomes() -> None:
    unmet = [s.expected_unmet for s in synthetic.load_scenarios()]
    assert any(not u for u in unmet)
    assert any(u for u in unmet)


def test_unknown_ids_raise_key_error() -> None:
    for loader in (synthetic.load_chart, synthetic.load_policy, synthetic.load_request):
        with pytest.raises(KeyError):
            loader("nope")
