# Forensa - Glossary

**Doc:** 20 of 22

Terms used across the Forensa doc pack. Listed alphabetically.

## A

**AAGATE** - Architecture for AI Agent Governance and Trust Enforcement; CSA Nov 2025 paper (arXiv 2510.25863) influencing Forensa design.

**Agent (DID-bound)** - An AI agent identified by a Decentralised Identifier with a registered Ed25519 public key. All actions are signed by the agent identity.

**AER (Agent Event Records)** - Oracle pattern for capturing AI reasoning chains. Adapted in BR-03.

**AgentCore (AWS Bedrock)** - AWS enforcement-focused runtime for Bedrock-hosted agents. Complementary to Forensa, not competitive.

**AGT (AI Governance Toolkit)** - Microsoft enforcement-focused control plane. Forensa sits behind it as evidence layer.

**AI EvidenceOps** - Forensa category framing. Sister to DevOps, SecOps, FinOps. The discipline of treating AI evidence as enterprise infrastructure.

**Alembic** - Python database migration tool. Used for PostgreSQL schema evolution.

**Article 12** - EU AI Act paragraph requiring automatic logging for high-risk AI systems. Effective August 2026. Forensas anchor regulation.

**Article 17 (GDPR)** - Right to erasure. Forensa handles via cryptographic shredding of per-record KMS data keys.

**Article 28 (GDPR)** - Processor obligations. Forensa is a data processor under tenant control.

**Article 30 (DORA)** - Digital Operational Resilience Act third-party ICT risk management. Triggers BR-12 tabletop mode.

**Article 32 (GDPR)** - Security of processing. Mapped to Forensa Security Architecture (doc 10).

**Article 33 (GDPR)** - 72-hour breach notification.

**asyncpg** - Async PostgreSQL driver for Python. Used in FastAPI ingest path.

## B

**BR-NN** - Business Requirement. Forensa has 13 (BR-01 through BR-13). See doc 02.

**BRD** - Business Requirements Document. Doc 02 of the pack.

**Bilateral ledger** - Year 4 moat concept: both Forensa and customer retain receipt history; switching cost grows with deployment age.

## C

**Chain (Merkle)** - Append-only hash-linked log of Receipts. Each Receipt holds previous_receipt_hash; daily Merkle root anchored to TSA.

**Cohort** - A query-defined set of Receipts (e.g. all credit decisions in Q1) used as input to evidence pack generation.

**Counterfactual narrative** - Gemini Pro generated explanation that includes what could have happened differently. Marked as interpretation, not source of truth.

**Credo AI** - AI governance platform. Complementary to Forensa (governance layer above runtime).

**CSDDD** - Corporate Sustainability Due Diligence Directive. Mentioned in commercial framing.

**CSRD** - Corporate Sustainability Reporting Directive. Triggers BR-05 reasonable-assurance reporting.

## D

**DID (Decentralised Identifier)** - W3C standard for agent identity. Each agent has a DID + Ed25519 public key.

**DLT** - Distributed Ledger Technology. Explicitly rejected in Forensa architecture; centralised Merkle is sufficient and performant.

**DORA** - Digital Operational Resilience Act (EU 2025+). Article 30 is Forensas financial-services anchor.

**DPA** - Data Processing Agreement (GDPR Article 28 mandatory).

**DPIA** - Data Protection Impact Assessment (GDPR Article 35).

## E

**Ed25519** - Elliptic curve signature algorithm. Used for all Forensa signatures (agent + tenant + tenant root).

**eIDAS** - EU electronic identification regulation. Ed25519 signatures binding under eIDAS.

**ESIGN** - US Electronic Signatures Act. Ed25519 signatures binding under ESIGN.

**Evidence Pack** - Signed bundle of Receipts + narrative + manifest + chain proofs. Per template (eu-ai-act-art12, nist, iso42001, etc.). See doc 12.

## F

**FastAPI** - Python web framework. Foundation of Forensa backend API.

**FCA** - UK Financial Conduct Authority. Canonical demo regulator.

**FIPS** - Federal Information Processing Standards. PyCA cryptography offers FIPS-validated build.

## G

**Gemini Pro** - Google long-context model. Used for narrative generation (BR-11) and counterfactual analysis.

**Gemini Flash** - Google fast model. Used for investigator natural-language UX (BR-10).

**Google AI Studio** - Customer-facing prompt-authoring tool. Used for custom regulator pack templates (BR-05).

**GR00T VLA** - NVIDIA Vision-Language-Action model. Stretch-goal reasoning evaluation evidence.

## H

**Hash chain** - Each Receipt holds SHA-256 of previous Receipt. Tampering with one Receipt breaks downstream chain.

**HDP** - Hierarchical Deterministic Path. Used for agent identity derivation (BR-02).

**HSM** - Hardware Security Module. Optional backing for tenant root keys (Regulated Enterprise tier+).

## I

**Ingest** - Path that captures AI events from agents. OTel GenAI semconv compatible.

**ISO 42001** - AI management system standard. Forensa BR-01, BR-04, BR-05 satisfy.

## J

**JSON-LD** - JSON for Linked Data. Evidence pack format (with PROV-O context).

## K

**Kafka** - Pluggable event bus option (BR-09). Alternative: AWS EventBridge.

**KDF** - Key Derivation Function. Forensa uses HKDF-SHA-256 for agent key derivation from tenant root.

**KMS** - Key Management Service (AWS, Azure, GCP). Holds tenant signing keys.

## L

**LangGraph** - Multi-agent workflow orchestrator. Used for provenance graph in BR-07.

**Langfuse / LangSmith / Logfire** - AI observability platforms. Forensa exports compatible; different buyer.

**Lobster Trap (Veea)** - Veea inline policy inspection product. Primary verdict source feeding Forensa receipts (BR-01, BR-04, BR-07).

## M

**MAR / Reg FD** - Market Abuse Regulation / Regulation Fair Disclosure. Pre-publication blackout enforcement use case.

**MCP (Model Context Protocol)** - Anthropic standard for tool integration. Forensa exposes MCP server for auditor portals (BR-05).

**Merkle tree** - Hash tree enabling efficient inclusion proofs. Built daily from Receipts; root anchored to TSA.

## N

**Narrative** - Human-readable summary generated by Gemini Pro (BR-11). Always marked as interpretation, not source of truth.

**Next.js 15** - React framework. Forensa investigator console (apps/console).

**NFR** - Non-Functional Requirement (latency, scale, security). See doc 02 NFR section.

**NIS2** - EU Network and Information Security Directive (2nd version). 24h incident reporting.

**NIST AI RMF** - US AI Risk Management Framework. Govern/Map/Measure/Manage functions.

## O

**Omniverse (NVIDIA)** - Digital twin platform. Stretch goal for BR-08 physical-action replay.

**OPA (Open Policy Agent)** - Policy engine. Forensa loads OPA bundles as policy snapshots (BR-04).

**OpenSearch** - Search backend for investigator queries (BR-10).

**OpenTelemetry** - Observability standard. GenAI semconv subset used as Forensa ingest wire format.

**OTel** - Shorthand for OpenTelemetry.

**OTLP** - OpenTelemetry Protocol (gRPC and HTTP/protobuf).

## P

**PII** - Personally Identifiable Information. Optionally hashed by Forensa PII redaction layer.

**Policy snapshot** - Frozen copy of OPA bundle hash at the moment of decision. Bound to Receipt for reconstruction (BR-04).

**PostgreSQL** - Primary database. Hot ledger (90 days) with monthly partitioning.

**Preloop** - AI runtime enforcement vendor. Complementary, not competitive.

**PROV-O** - W3C provenance ontology. Used in evidence pack JSON-LD.

**Pydantic v2** - Python validation library. All schemas in packages/schema.

## R

**Receipt** - Core Forensa entity. Tamper-evident, dual-signed, policy-bound record of an AI action. See doc 09.

**Replay** - Reconstruction of decision context as of a Receipts timestamp. Includes policy snapshot, model version, tool catalog.

**RFC 3161** - IETF Time-Stamping Authority Protocol. Used for daily Merkle root anchoring.

**RFC 6962** - Certificate Transparency Merkle Inclusion Proof format. Used for chain proofs in evidence packs.

## S

**SaaS** - Software as a Service. Default Forensa deployment mode for Year 1.

**SBOM** - Software Bill of Materials. CycloneDX format, signed per release.

**SHA-256** - Hash algorithm. Used throughout for content hashing and Merkle tree.

**SIEM** - Security Information and Event Management (Splunk, Sentinel, QRadar). Forensa exports compatible.

**SLO** - Service Level Objective. See doc 18.

**SOC 2 Type II** - AICPA Trust Services Criteria audit. Forensa Year 2 target.

**SQLAlchemy 2.0** - Python ORM. Used with asyncpg.

**SSO** - Single Sign-On. Forensa supports OIDC and SAML.

**STRIDE** - Threat modelling framework (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege). See doc 11.

## T

**Tabletop** - Synthetic incident response exercise (BR-12). DORA Article 30 requirement.

**Tamper detection** - Forensa core demo. Modified Receipt fails chain verification within seconds.

**TechEx** - Google Intelligent Enterprise Solutions Hackathon (May 11-19, 2026). Forensa submission target.

**Tenant** - Customer organisation. Per-tenant signing keys, KMS, retention policy.

**TLPT** - Threat-Led Penetration Testing (DORA Article 30 requirement).

**TLS 1.3** - Transport Layer Security. Enforced for all Forensa connections.

**TSA** - Time-Stamping Authority. External RFC 3161 service. Forensa uses 2+ for quorum.

## U

**UC-NN** - Use Case. Forensa has 8 (UC-01 through UC-08). See doc 05.

**UUIDv7** - Time-ordered UUID. Used for all Forensa primary keys.

## V

**Veea** - Hackathon sponsor; Lobster Trap product is verdict source.

**Verifier (forensa-verify)** - Open-source MIT-licensed utility for regulators to verify evidence packs without Forensa account.

## W

**watsonx.governance** - IBM AI governance platform. Complementary to Forensa.

**Webhook** - Forensa event notification. See doc 08 webhooks table.

## X

**XMPro** - Digital twin orchestration. Stretch goal for BR-08 with DT Consortium.

