# DPIA addendum - Debattanalys module

**Status:** SKELETON / draft. Version 0.1.
**Owner:** [DATA PROTECTION OWNER]

> **DRAFT - NOT LEGAL ADVICE.** Complements [`docs/dpia.md`](./dpia.md), which
> covers only user-submitted text. The debate module processes something
> different: recorded audio/video of **identified public figures**, transcribes
> what they said, and **publishes** automated truthfulness verdicts about their
> statements. That is a distinct processing activity and needs its own
> assessment before anything goes public.

## 1. What is different from the main app

| Main app (dpia.md) | Debate module (this addendum) |
| --- | --- |
| Data subjects are our users | Data subjects are politicians and moderators appearing in broadcasts |
| Text submitted voluntarily by the user | Broadcast audio/video obtained from SVT / Riksdagen |
| Results shown privately to one user | Verdicts published for anyone to watch |
| Art. 9 risk: users' own political opinions | Art. 9 data: political opinions of the speakers, inherently and intentionally |

## 2. Description of the processing

- **Nature:** download published debate broadcasts; extract audio; transcribe
  via Azure AI Speech (EU region, `sv-SE`) with speaker diarization; map
  speakers to named politicians; extract factual claims; verify them with AI
  models and web search; publish a timeline of verdicts with sources.
- **Data categories:** voice recordings, transcribed statements, speaker
  identity and party, automated truthfulness assessments. Political opinions
  are the subject matter itself (Article 9).
- **Storage:** original video/audio kept only as internal processing artifacts
  in `debatt/data/` [define location and retention]. Published artifact is
  `timeline.json` (text only, no audio/video). SVT video is never rehosted.
- **Processors:** Microsoft (Azure Speech, [confirm EU region and DPA]),
  Anthropic (claim extraction/verification, [DPF/SCC status]), web search
  provider(s), hosting for the published viewer [TBD].

## 3. Lawful basis - to be assessed

Candidate reasoning, to be confirmed with qualified support:

- The statements are made by **public figures in their public role**, in
  broadcasts intended for mass distribution. The speakers have manifestly made
  these political opinions public themselves (**Art. 9(2)(e)**).
- Processing for **journalistic purposes**: fact-checking political debate is
  a recognized journalistic activity; Swedish law (Ch. 1, § 7 dataskyddslagen)
  gives broad exemptions for journalistic processing. [Assess whether the
  project qualifies and document.]
- Legitimate interest (Art. 6(1)(f)): public interest in accurate political
  discourse; balancing test against the speakers' rights. [Write the LIA.]
- **Copyright is separate from GDPR:** downloading and processing SVT material
  internally vs republishing it are different questions. The module never
  republishes video; [assess quoting rights for short `citat` strings].

## 4. Risks specific to this module

- **Wrong verdict published about a named person** (defamation-adjacent,
  reputational harm). Highest severity risk of the whole project.
- ASR mis-transcription changes the meaning of a statement (numbers, negations).
- Diarization/mapping attributes a statement to the wrong politician.
- Systematic bias: one party's statements rated harsher than another's.
- Over-retention of raw broadcast material without purpose.

## 5. Mitigations

- Adversarial review pass on every harsh verdict before publication
  (`FALSKT`, `MESTADELS FALSKT`, `VILSELEDANDE`), see
  [`docs/debatt-arkitektur.md`](./debatt-arkitektur.md) section 4.
- Human review of the full timeline for at least the pilot debates.
- Every event carries `citat` (what was actually said), sources, and an
  `osakerhet` field; the mandatory disclaimer states verdicts are automated
  and not authoritative.
- Same-yardstick instruction ("Granska alla partier med samma måttstock")
  retained from the main prompts; [consider a per-debate bias check comparing
  verdict distributions across parties].
- **Correction routine (required before publication):** a public contact
  point, a commitment to review disputed verdicts within [X days], and
  published errata; corrected timelines are re-published with a changelog.
- Retention: raw video/audio deleted [X months] after the timeline is
  published; transcripts kept as working material [define].
- EU processing regions for ASR and hosting; DPAs with all processors.

## 6. Residual risk and sign-off

- [Assess after mitigations. If high, prior consultation with IMY (Art. 36).]
- Sign-off: [name, role, date].

## 7. Review triggers

New source types (e.g. Riksdag webb-tv), any change of ASR or AI provider,
any move from internal pilot to public publication, and at least annually.
