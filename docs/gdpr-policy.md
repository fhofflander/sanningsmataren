# GDPR / Data Protection Policy - Sanningsmätaren

**Effective date:** [EFFECTIVE DATE]
**Version:** 1.0 (draft)
**Owner:** [DATA PROTECTION OWNER / ROLE]

> **DRAFT - NOT LEGAL ADVICE.** This is an internal-facing data protection policy
> drafted to sit alongside the user-facing [Privacy Policy](./privacy-policy.md).
> It has **not** been reviewed by a qualified data protection professional.
> Because Sanningsmätaren processes special category data (political opinions,
> Article 9), a **Data Protection Impact Assessment (DPIA)** is very likely
> mandatory under Article 35 before launch. Treat the sections below as a
> structured starting point, not a finished compliance position.

## 1. Purpose and scope

This policy sets out how the Sanningsmätaren team handles personal data in line
with the EU General Data Protection Regulation (GDPR) and the Swedish
supplementary data protection law. It applies to everyone who builds or operates
the Service and to all personal data the Service processes.

## 2. Roles and responsibilities

- **Data controller:** [COMPANY LEGAL NAME] (confirm whether single or joint
  controller with AltCtrlAB under Article 26).
- **Data protection point of contact:** [NAME / ROLE / EMAIL].
- **Data protection officer:** [APPOINTED? If processing is large-scale and
  systematic monitoring or large-scale special category data, a DPO may be
  mandatory under Article 37 - assess and record the decision here.]
- **Processors engaged:** Vercel, Google, Anthropic, Brave (see section 7).

## 3. Data protection principles (Article 5)

We commit to processing personal data:

1. lawfully, fairly, and transparently;
2. only for the specified purposes in section 5;
3. limited to what is necessary (data minimisation);
4. accurately, keeping it up to date;
5. for no longer than needed (see retention, section 8);
6. securely (section 9);
7. with accountability - we keep the records this policy describes.

## 4. Lawful bases

| Processing activity | Art. 6 basis | Art. 9 condition (if special category) |
| --- | --- | --- |
| Authentication and core service | Contract (6(1)(b)) | n/a |
| Daily quota / abuse prevention | Legitimate interests (6(1)(f)) | n/a |
| Logging questions and answers | Consent (6(1)(a)) | Explicit consent (9(2)(a)) |
| Security and fraud prevention | Legitimate interests (6(1)(f)) | n/a |

A Legitimate Interests Assessment (LIA) should be recorded for each (6(1)(f))
activity. A record of the explicit consent mechanism (wording, timestamp, how it
is withdrawn) must be kept for the logging activity.

## 5. Special category data and DPIA

The content users submit can reveal political opinions (Article 9 data).
Consequences:

- Processing requires **explicit consent** (9(2)(a)) and the consent must be
  separable, specific, and as easy to withdraw as to give.
- A **DPIA (Article 35)** should be completed and documented before launch,
  covering: the nature and scope of processing, necessity and proportionality,
  risks to data subjects, and mitigations. [Link the DPIA here once written.]
- Data minimisation matters more here: log only what quality review genuinely
  needs, and consider pseudonymising the user identifier in logs.

## 6. Records of processing (ROPA summary)

| Activity | Data subjects | Data categories | Purpose | Recipients | Retention |
| --- | --- | --- | --- | --- | --- |
| Authentication | Users | Google ID, email | Operate service | Vercel, Google | Account life + [X] |
| Fact-check requests | Users | Submitted text (Art. 9), results | Provide checks | AI/search providers | Not stored beyond request unless logged |
| Logging | Users | Questions, answers, user ID | Quality review | Vercel | [12 months] |
| Quota | Users | Per-day counts | Limit usage | Vercel | Daily reset |

Keep this table current; it is the Article 30 record of processing.

## 7. Processors and international transfers

- All processors must be under a **data processing agreement (Article 28)**.
- Confirm and record each processor's transfer safeguard (EU-US Data Privacy
  Framework certification or Standard Contractual Clauses) for any processing
  outside the EEA.
- Where a provider offers EU data residency (for example Vercel function/region
  and database region), prefer it and record the choice.

## 8. Retention schedule

Apply the retention periods in the [Privacy Policy](./privacy-policy.md)
section 8. Build automated deletion or anonymisation jobs so retention is
enforced in practice, not just on paper. Record the retention rationale for each
data category.

## 9. Data subject requests

- Requests (access, erasure, rectification, restriction, portability, objection,
  consent withdrawal) go to **[PRIVACY CONTACT EMAIL]**.
- Respond within **one month** (extendable by two months for complex requests,
  with notice).
- Verify the requester's identity proportionately before disclosing data.
- Maintain a log of requests and how they were handled.

## 10. Personal data breach procedure

- On discovering a suspected breach, contain it and assess the risk to
  individuals.
- If the breach is likely to result in a risk to people's rights and freedoms,
  notify **IMY within 72 hours** of becoming aware (Article 33).
- If the risk is high, notify affected users without undue delay (Article 34).
- Record every breach, its effects, and the remedial action (internal breach
  register), whether or not it was notifiable.

## 11. Security measures

- API keys and provider credentials are kept server-side only, never shipped in
  the extension or web bundle.
- Encryption in transit (HTTPS) for all requests.
- Access to the backend, database, and logs is restricted to authorised team
  members and reviewed periodically.
- Principle of least privilege for service accounts and tokens.
- All client JavaScript is bundled in the package; no remote code execution.

## 12. Review

Review this policy and the ROPA at least annually, and whenever the architecture
or data flows change materially (for example a new provider, a new data
category, or a change to retention). Record the date and outcome of each review.

---

**Related documents:** [Privacy Policy](./privacy-policy.md) -
implementation issues #9 (backend), #10 (auth + quota), #11 (logging + GDPR).
