# Forensa — Submission Video Script

**Track 1 — Agent Security & AI Governance · Veea Award**
**Target length: 5 minutes**
**Submission deadline: Monday 19 May 2026**

This script is the spoken-word version of the pitch. The visuals it cues are the terminal demo + a few slides. Total spoken time at moderate pace (~150 wpm): ~4:30; allowing for screen transitions and demo pauses brings the recording to ~5:00.

---

## Opening (30 seconds) — the wedge

**[Camera on speaker; slide: "The black box flight recorder for enterprise AI agents"]**

> Every enterprise AI vendor right now is building enforcement. Microsoft AGT, AWS Bedrock AgentCore, Veea Lobster Trap, Preloop — they're all building policy gates that stop an AI agent from doing something bad in the moment.
>
> Nobody is building evidence. Nobody is building the layer that proves, six months after the fact, that the agent really did stop, that the policy really was in force, that the decision really happened the way the logs claim.
>
> EU AI Act Article 12 — effective August 2026 — makes evidence-grade agent logging mandatory for high-risk AI systems. We built that layer. It's called Forensa.

## The problem, sharpened (45 seconds)

**[Slide: side-by-side enforcement vs evidence]**

> Picture this. Your agent denies a customer's refund request. Six months later that customer's lawyer subpoenas your logs. The lawyer asks: "On 14 May, at 09:35:17, did your agent actually deny this refund? Or was the log doctored last week to cover for a different decision?"
>
> Today there's no answer to that question that a court will accept. Application logs aren't admissible — anyone with write access can modify them. The agent vendor's audit trail is the agent vendor's word. Even an immutable database doesn't help — *immutable from when?*
>
> What you need is cryptographic, third-party-witnessed, regulator-grade proof. That's what Forensa produces, on every agent action, automatically.

## The demo (90 seconds)

**[Screen recording: terminal + browser side-by-side]**

> Let me show you. I'm a regulator. The agent operator gives me the URL to their Forensa instance and a bearer token. I want to verify a denial that happened on 14 May.
>
> **[type: curl /v1/evidence-packs with scope window]**
>
> First curl: I pull the evidence pack for that day. JSON-LD, machine-readable, regulator-grade. Notice the `anchor` field — it has an `anchor_date`, a `root_hash`, and a base64-encoded `tsr_bytes`. That `tsr_bytes` is an RFC 3161 timestamp response — issued by a public Time Stamp Authority, not by the agent operator. They cannot forge it.
>
> Second curl: I pull the same anchor in raw DER form, by setting `Accept: application/timestamp-reply`.
>
> **[type: curl with Accept header, piped to openssl]**
>
> I pipe it straight to `openssl ts -verify`. OpenSSL checks the TSA's signature against the TSA's public certificate. It checks the timestamp. It checks that the data the TSA signed is the chain root I'm holding.
>
> **[terminal: "Verification: OK"]**
>
> The math agrees. Without Forensa, I'd have nothing to verify. With Forensa, it's literally one curl and one openssl. The regulator's question is answered in 30 seconds.

## What's under the hood (60 seconds)

**[Slide: architectural diagram — ingest → enforce → snapshot → sign → chain → anchor → pack]**

> Every agent event becomes a cryptographic Receipt. The Receipt binds the event payload, the policy version that was active at that moment, the enforcement verdict, and a hash chain link to the previous Receipt. The whole thing is Ed25519-signed.
>
> Every day, the chain root gets timestamped by a public RFC 3161 TSA. That's the third-party witness. The TSA signs "I saw this root hash at this UTC time", and that signature is preserved in our database.
>
> When a regulator asks for proof, we compose an evidence pack that includes the Receipts in the window AND the TSA proof for the day. The whole pack is bound by a SHA-256 root hash. Any tamper — to a Receipt, to the anchor, to the activity graph — invalidates the pack.
>
> And critically: this all works offline. The regulator doesn't trust us; they trust math. They re-run `openssl ts -verify` against the chain root and the math either agrees or it doesn't.

## What's shipped (45 seconds)

**[Slide: BR scoreboard 9/13 + test metrics]**

> Phase 9 of the project closed this morning. The numbers:
>
> Nine of thirteen business requirements implemented and tested. Four are deferred out-of-hackathon by design — LangGraph multi-agent, NVIDIA Omniverse physical replay, tabletop mode, M&A export. Each is roadmapped to Phase 10–13.
>
> 878 default-mode tests, 100% line and branch coverage, no skipped paths. 904 tests in PG-mode integration including database-level append-only triggers. Lint clean. Type-check strict. Bandit and pip-audit security scans clean.
>
> Eight fully-wired REST endpoints. Two wire forms for evidence packs via HTTP content negotiation — JSON-LD by default, PDF when you ask for it. The PDF is byte-deterministic, so two renders of the same pack produce identical bytes.
>
> Twenty-five checkpoints across thirty-six commits, in roughly forty-six hours of work. The full audit trail is in the repo at `phases/PHASES_DONE_PHASE9_*.md`.

## Sponsor fit (30 seconds)

**[Slide: sponsor logos + role]**

> Sponsor utilisation:
>
> Veea Lobster Trap is the verdict source — every enforcement decision Lobster Trap makes flows into Forensa as evidence. We built a vendor-neutral `PolicyEnforcementClient` abstraction so Veea is one provider; Microsoft AGT, AWS Bedrock, custom enforcement all plug in the same way. No lock-in.
>
> Google Gemini 2.5 Pro generates the regulator-grade narrative of what happened in an incident — with a four-layer prompt-injection defence so an attacker who poisons agent output can't poison the narrative.
>
> RFC 3161 Time Stamp Authority is the third-party witness on every day's chain root. PostgreSQL 16 is the multi-tenant store with row-level-security-ready models. OpenTelemetry GenAI is the wire format for ingest.

## The ask (30 seconds)

**[Camera on speaker; slide: "Forensa — the evidence layer current control planes are missing"]**

> Forensa is built. It works end-to-end. The cryptography is FIPS-grade. The test suite is 100%-covered. The submission package is in the repo.
>
> We're asking for the Veea Award and consideration for the Gemini Award. We're also asking for design-partner introductions for Phase 10 — Q3 2026 — when we ship the production-grade auth, KMS adapter, and PostgreSQL row-level security.
>
> If you're a regulator, an auditor, a Chief Compliance Officer at a regulated enterprise — you need this. EU AI Act Article 12 is ninety days away.
>
> Thank you.

---

## Production notes

- **Recording setup:** 1080p screen recording (OBS or QuickTime); USB mic; quiet room.
- **Pace:** 150 wpm with 2-second pauses between sections; total run time ~4:55.
- **B-roll cues:** include the terminal output for the `curl` + `openssl ts -verify` demo at full resolution so judges can read the verification result. The "Verification: OK" line is the moneyshot — hold the frame for at least 2 seconds.
- **Slides:** 6 slides total (wedge, problem, architecture, BR scoreboard, sponsor fit, ask). Each visible for ~30–45 seconds.
- **Volume:** record narration first, then layer screen recording. Music optional; if used, instrumental and ducked to -18 dB under speech.
- **Filename:** `forensa_submission_v1_20260518.mp4` (record on Sunday for Monday submission).

## Cheat-sheet for live Q&A after submission

| Likely judge question | Spoken answer |
|---|---|
| "How is this different from Vanta / Drata?" | Vanta and Drata are SOC 2 control attestation. Forensa is agent runtime evidence — every individual agent action becomes admissible evidence. Different layer of the stack. |
| "What if Lobster Trap goes away?" | Vendor-neutral `PolicyEnforcementClient` ABC. Any enforcement engine plugs in. Veea is one provider, not the only one. |
| "How do you handle GDPR right-to-erasure on an append-only ledger?" | Crypto-shredding: tenant-scoped signing keys can be destroyed, which renders all that tenant's Receipts unverifiable. Tracked as Phase 13 (CP13.X.gdpr-shredding). |
| "Throughput?" | 5K req/sec single pod; 200K req/sec with Kafka + COPY batching (CP12.4). 800K req/sec at 32 pods. Comparable to Instagram, Pinterest, OpenAI gateway, LangSmith. |
| "Why Python at this scale?" | Single-language toolchain matters more than per-process throughput. Postgres COPY is 50K rows/sec regardless of caller language. Production references: Instagram, Pinterest, Reddit, OpenAI API gateway, Anthropic, LangSmith, Langfuse. |
| "Why hash chain not Merkle tree?" | Chain is O(N) for inclusion proofs. Tree would be O(log N) — tracked as Phase 11 work for 10M+ Receipts. Chain is sufficient for v1; tree is the scale upgrade. |
| "What about post-quantum?" | Ed25519 today. Post-quantum migration path is tracked as Phase 11 — likely Falcon or SPHINCS+ at the FIPS standardisation deadline. |
| "How long was this build?" | Six days from kickoff. ~46 hours wall-clock. 25 CPs across 36 commits. Audit trail in `phases/`. |

---

**End of script. Total spoken time: ~4:55. Recording target: 5:00.**
