# prior-auth-agent

An AI agent that drafts **prior authorization letters** from a patient chart and payer rules, for a
clinician to review and sign.

It pulls the relevant chart history and the payer's coverage criteria through typed tools, checks which
criteria are met, and writes a draft letter that cites its evidence. A human always approves before
anything is sent.

All data in this repo is **synthetic**. No real patient data is used.

> Status: early development.

## License

[MIT](LICENSE)
