# Forensa - Evidence Pack Specification

**Doc:** 12 of 22 | **Source:** Section A.8, B.14 of master doc

## What is an Evidence Pack?

A regulator-grade, cryptographically-signed bundle that answers "what did this AI system do, on whose authority, under which policies, and how do we know it's authentic". Built from a cohort of Receipts + narrative + provenance + manifest.

## Pack structure

```
evidence-pack-{pack_id}.tar.gz
├── manifest.json.signed         <- top-level signed manifest
├── narrative.md                  <- Gemini Pro generated human-readable summary
├── narrative.pdf.signed         <- PDF with embedded signature
├── receipts/
│   ├── receipt-{id1}.jsonld.signed
│   ├── receipt-{id2}.jsonld.signed
│   └── ...
├── policies/
│   ├── policy-bundle-{hash1}.json
│   └── policy-bundle-{hash2}.json
├── chain/
│   ├── merkle-proof.json        <- inclusion proof for every receipt in pack
│   └── tsa-anchors.bin          <- RFC 3161 TSA responses
├── provenance/
│   └── prov-o.jsonld            <- W3C PROV-O ontology graph
└── README.md                     <- regulator-readable description
```

## Manifest format (JSON-LD with PROV-O context)

```json
{
  "@context": "https://www.w3.org/ns/prov",
  "@id": "urn:forensa:pack:{pack_id}",
  "@type": "prov:Bundle",
  "prov:generatedAtTime": "2026-05-13T10:30:00Z",
  "forensa:template": "eu-ai-act-art12",
  "forensa:tenant": "...",
  "forensa:cohort_filter": { ... },
  "forensa:receipt_ids": [...],
  "forensa:narrative_hash": "sha256:...",
  "forensa:chain_root_at_pack_time": "sha256:...",
  "forensa:tsa_anchor_id": "...",
  "forensa:signature": {
    "alg": "Ed25519",
    "key_id": "tenant-key-2026Q2",
    "signature": "base64:..."
  }
}
```

## Templates (BR-05)

### EU AI Act Article 12 (eu-ai-act-art12)
Sections mapped to Article 12 paragraph requirements:
1. Period of use - timeline from earliest to latest receipt
2. Reference databases - policy bundles in effect
3. Input data resulting in match - prompt hashes + reasoning chain
4. Natural persons involved - human approvers + reviewers

### NIST AI RMF (nist-ai-rmf)
Sections mapped to RMF functions: Govern, Map, Measure, Manage.

### ISO 42001 (iso-42001)
Sections mapped to ISO 42001 clauses including Clause 8 (operation) and Clause 9 (performance evaluation).

### SOC 2 Type II (soc2-type2)
Trust Services Criteria: Security, Availability, Processing Integrity, Confidentiality, Privacy.

### HIPAA (hipaa)
Audit log retention (6 years), PHI handling provenance.

### DORA Article 30 (dora-art30)
ICT third-party register entries + tabletop exercise evidence.

### MAR / Reg FD (mar-reg-fd)
Pre-publication blackout enforcement, selective disclosure prevention.

### Custom (custom)
Customer-authored template via Google AI Studio. Customer designs the prompt that Gemini Pro uses to generate the narrative; Forensa enforces the structural manifest fields.

## Verification utility

Open-source verifier `forensa-verify` (Python, MIT-licensed):
```
$ forensa-verify evidence-pack-abc.tar.gz
[OK] Manifest signature valid
[OK] All receipt signatures valid
[OK] Merkle inclusion proofs valid
[OK] TSA anchor valid (eu-tsa.example.com, 2026-05-13)
[OK] PROV-O graph well-formed
[OK] Narrative hash matches narrative content
RESULT: PACK VERIFIED
```

Verifier is the regulator's primary entry point. No Forensa account needed.

## Narrative generation (BR-11)

Gemini Pro receives:
- Receipts (raw)
- Policy bundles
- Template-specific system prompt
- Hallucination guardrails (no claims beyond what receipts contain)

Output: regulator-readable markdown + PDF. Marked clearly as "interpretation; not source of truth - see receipts/ for cryptographic chain".

## Chain proof generation

For each Receipt in pack:
1. Compute Merkle path from leaf to root
2. Include sibling hashes
3. Include TSA-anchored root at time of receipt
4. Optionally include subsequent TSA anchors (long-term proof)

Standard format: RFC 6962 Merkle Inclusion Proof.

## Retention

Evidence packs themselves are retained per tenant policy. Each pack export is also a Receipt (introspection - BR-01 covers Forensa's own operations).

## Performance targets

- Pack generation for 1000 receipts: <5 minutes
- Verification of 1000-receipt pack: <30 seconds on commodity laptop
- Pack size for 1000 receipts: ~50MB (compressed, signatures included)
