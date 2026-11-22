# prior-auth-agent

An AI agent that drafts **prior authorization letters** from a patient chart and payer rules, for a
clinician to review and sign.

It pulls the relevant chart history and the payer's coverage criteria through typed tools, checks which
criteria are met, and writes a draft letter that cites its evidence. A human always approves before
anything is sent.

All data in this repo is **synthetic**. No real patient data is used.

> Status: early development.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scriptsctivate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Domain model

Typed, immutable Pydantic models in `prior_auth_agent.models`:

- **Chart:** `Patient` (synthetic `SYN-xxxxx` IDs only), `Diagnosis` (validated, normalized
  ICD-10-CM codes with onset/resolution dates), `Medication` trials with a `StopReason`,
  `LabResult`, `Encounter` (with specialty) and documented `Contraindication`s. Helpers answer
  the questions a reviewer asks: active diagnoses under a code category, trials of a drug class,
  the latest lab before a date, recent visits with a specialty.
- **Payer policy:** a list of typed criteria, each with a stable `id` so a letter can cite exactly
  what it satisfies: `diagnosis`, `age`, `lab` (threshold within N days), `step_therapy` (trial of a
  preferred drug class for N days, or intolerance, or contraindication) and `specialist`.
- **AuthRequest:** one drug, one patient, one policy, on a given date.

## Synthetic data

`prior_auth_agent.synthetic` loads the bundled fixtures: two policies from a fictional payer and five
charts, each with a request and the criteria it is expected to miss.

| Request | Drug | Expected | Why |
|---|---|---|---|
| PA-0001 | semaglutide | approve | Long metformin trial failed, recent HbA1c 8.6% |
| PA-0002 | semaglutide | missing `metformin-trial` | Metformin started 44 days ago |
| PA-0003 | semaglutide | missing `a1c` | Metformin contraindicated (CKD 4) counts, but HbA1c is stale |
| PA-0004 | adalimumab | approve | 7-month methotrexate trial failed, recent rheumatology visit |
| PA-0005 | adalimumab | missing `rheumatology` | Methotrexate intolerance counts, but no rheumatology visit in 180 days |

## License

[MIT](LICENSE)
