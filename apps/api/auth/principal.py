"""apps.api.auth.principal — the unit of authenticated identity in Forensa.

A ``Principal`` is the resolved-from-token identity that the API operates on.
It is intentionally minimal: tenant_id, agent_id (the AI agent acting on
behalf of the tenant), the agent's slug (human-readable), and a set of
opaque scope strings.

CP9.18b / BR-02. The Principal is consumed by:

- Routes (CP9.18c) - to refuse posts where ``event.tenant_id != principal.tenant_id``
  or ``event.agent_id != principal.agent_id``.
- AgentSigningKeyProvider (today: ``InMemoryAgentSigningKeyProvider`` keyed by
  agent_id; CP11.1: KMS adapter resolving by ``Principal.agent_id``).

Principal is **frozen**. The route layer constructs it once per request via
``Depends(get_principal)``; downstream code cannot mutate it. Equality is
structural so test fixtures can build expected Principals and compare.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Resolved-from-token authenticated identity.

    Attributes
    ----------
    tenant_id : UUID
        The tenant this principal acts on behalf of. Receipt + event writes
        scoped to this tenant ONLY.
    agent_id : UUID
        The agent's identifier. Used to resolve the agent's Ed25519 signing
        key via ``AgentSigningKeyProvider`` for the dual-signature
        receipt path (CP9.18 / BR-02).
    agent_slug : str
        Human-readable agent identifier, eg ``acmecorp-research-agent-v3``.
        Mirrors ``Agent.slug`` from ``packages.schema.agent``. Useful in
        audit logs without resolving back to the DB.
    scopes : frozenset[str]
        Opaque permission scopes carried in the token. Routes that need
        coarse-grained authorization beyond tenant/agent match (eg
        ``narratives:generate`` vs ``receipts:read``) check membership here.
        Empty frozenset is the default - the route layer treats this as
        "tenant+agent match is sufficient" for endpoints without a scope
        requirement.
    """

    tenant_id: UUID
    agent_id: UUID
    agent_slug: str
    scopes: frozenset[str] = field(default_factory=frozenset)

    def has_scope(self, scope: str) -> bool:
        """Return True iff ``scope`` is in this Principal's scopes."""
        return scope in self.scopes
