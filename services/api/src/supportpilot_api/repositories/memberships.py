"""Membership lookup — how a verified subject becomes a tenant and a set of roles.

This is the only read that happens before tenant context exists. It runs with `app.user_id` set and
`app.organization_id` unset, and the `memberships_self` row policy limits it to the caller's own
rows.

Roles come from here, never from the token (`TS1-10`).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db import Database


@dataclass(frozen=True)
class Subject:
    """The authenticated caller, as the server understands them."""

    user_id: str
    identity_subject: str
    display_name: str
    memberships: dict[str, list[str]]  # organization_id -> roles
    authentication_level: str

    @property
    def organizations(self) -> list[str]:
        return sorted(self.memberships)

    def roles_in(self, organization_id: str) -> list[str]:
        return sorted(self.memberships.get(organization_id, []))

    @property
    def all_roles(self) -> list[str]:
        return sorted({role for roles in self.memberships.values() for role in roles})


_LOAD_SUBJECT = """
SELECT user_id::text         AS user_id,
       identity_subject      AS identity_subject,
       display_name          AS display_name,
       organization_id::text AS organization_id,
       role                  AS role
FROM app.resolve_subject(%s)
"""


class MembershipRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def load_subject(self, identity_subject: str, authentication_level: str) -> Subject | None:
        """Return the caller, or None when the subject has no active application user.

        A user with no active membership is returned with an empty membership map rather than None.
        They are authenticated but have access to nothing, and policy states that as
        `role_not_permitted_for_action` — a real answer, not a lookup failure.
        """
        with self._db.transaction(user_id=None, organization_id=None, read_only=True) as cur:
            # app.resolve_subject is the one narrow definer function that can answer "who is this
            # Keycloak subject". See migration 0002 for why the row policies cannot serve this.
            cur.execute(_LOAD_SUBJECT, (identity_subject,))
            rows = cur.fetchall()

        if not rows:
            return None

        memberships: dict[str, list[str]] = {}
        for row in rows:
            org = row["organization_id"]
            if org is None:
                continue
            memberships.setdefault(org, []).append(row["role"])

        first = rows[0]
        return Subject(
            user_id=first["user_id"],
            identity_subject=first["identity_subject"],
            display_name=first["display_name"],
            memberships=memberships,
            authentication_level=authentication_level,
        )
