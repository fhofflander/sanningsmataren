# Data Protection Impact Assessment (DPIA) - Sanningsmätaren

**Status:** SKELETON / draft. Version 0.1.
**Owner:** [DATA PROTECTION OWNER]

> **DRAFT - NOT LEGAL ADVICE.** This is a structured skeleton to be completed and
> signed off with qualified data protection support before launch. Because the
> Service processes special category data (political opinions, Article 9), a DPIA
> is very likely mandatory under Article 35. Fill each section; do not treat the
> headings alone as compliance.

## 1. Why a DPIA is needed

Processing involves special category data (political opinions) and is offered to
the public at scale, which triggers Article 35. Record the screening decision
and date here.

## 2. Description of the processing

- **Nature:** users submit Swedish political text; the backend uses AI models and
  web search to return sourced verdicts; questions and answers are logged with
  consent.
- **Scope:** data categories, volume, frequency, geographic reach, number of data
  subjects. [Fill in.]
- **Context:** public users, Swedish political discourse, BYOK replaced by a
  company-funded backend with Google sign-in.
- **Purposes:** provide fact-checking; enforce fair-use quota; improve quality
  through logging.

Data flow:
```
Extension/SPA --(Google id_token)--> Backend (EU region) --(company key)--> AI / search providers
                                         |
                                         +-- quota check (Redis/Postgres)
                                         +-- log question + answer (consent-gated, Postgres)
```

## 3. Necessity and proportionality

- Lawful bases: contract (service), legitimate interests (quota/abuse), explicit
  consent (logging). [Reference `docs/gdpr-policy.md` section 4.]
- Is logging necessary for the stated purpose, or could a sample / shorter
  retention / pseudonymised form achieve it? [Assess.]
- Data minimisation and storage limitation measures. [List.]

## 4. Data subjects and data categories

| Data subject | Categories | Special category? |
| --- | --- | --- |
| Users | Google id, email | No |
| Users | Submitted text, verdicts | Yes (political opinions, Art. 9) |
| Users | Usage counts, technical metadata | No |

## 5. Risks to data subjects

- Re-identification of sensitive political views from logged content.
- Inadvertent inference or profiling.
- Unauthorised access / data breach exposing sensitive text.
- Third-country transfer to US-based providers.
- Over-retention beyond the stated purpose.
- Consent not being freely given or easy to withdraw.

## 6. Risk assessment

| Risk | Likelihood | Severity | Overall |
| --- | --- | --- | --- |
| [risk] | low/med/high | low/med/high | [score] |

[Complete the table.]

## 7. Mitigations

- Explicit, separable, withdrawable consent before any logging.
- Data minimisation; consider default pseudonymisation of logs.
- Defined retention with automated deletion/anonymisation jobs.
- Encryption in transit; access controls and least privilege on the backend.
- EU data residency (host region and database region).
- Data processing agreements and transfer safeguards (DPF/SCC) with all
  processors (Vercel/host, Google, Anthropic, Brave).
- Keys server-side only; no remote code in the extension.

## 8. Residual risk and sign-off

- Residual risk after mitigations: [low/medium/high].
- If high, **prior consultation with IMY** is required before processing
  (Article 36).
- Sign-off: [name, role, date].

## 9. Review

Review on any material change to data flows, providers, retention, or purposes,
and at least annually. Record review dates and outcomes.
