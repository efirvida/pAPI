from sqlalchemy import Column, Integer, String, UniqueConstraint

from .base import Base


class AuthRules(Base):
    """SQLAlchemy model for Casbin policy rules storage.

    This model stores both policy rules (p) and role inheritance rules (g).
    The column names (v0-v5) follow Casbin's conventions:

    For policy rules (ptype='p'):
        - v0: subject (user or role)
        - v1: object (resource)
        - v2: action
        - v3: condition (optional)
        - v4: effect (allow/deny)
        - v5: additional info (optional)

    For role rules (ptype='g'):
        - v0: user or role
        - v1: role to inherit from
        - v2-v5: not used
    """

    __tablename__ = "auth_rules"

    id = Column(Integer, primary_key=True)
    ptype = Column(
        String(255), nullable=False, comment="Rule type: 'p' for policy, 'g' for role"
    )
    v0 = Column(String(255), nullable=False, comment="Subject/User")
    v1 = Column(String(255), nullable=False, comment="Object/Role")
    v2 = Column(String(255), comment="Action")
    v3 = Column(String(255), comment="Condition")
    v4 = Column(String(255), comment="Effect")
    v5 = Column(String(255), comment="Additional data")

    def __str__(self):
        """Returns a human-readable representation of the rule.

        For policy rules: "p, subject, object, action[, condition][, effect]"
        For role rules: "g, user, role"
        """
        components = [self.ptype]
        for v in (self.v0, self.v1, self.v2, self.v3, self.v4, self.v5):
            if v is None:
                break
            components.append(v)
        return ", ".join(components)

    def __repr__(self):
        """Returns a detailed string representation for debugging."""
        return f'<AuthRules {self.id}: "{str(self)}">'

    __table_args__ = (
        # Ensure uniqueness of policy rules (excluding id and v5)
        UniqueConstraint(
            "ptype",
            "v0",
            "v1",
            "v2",
            "v3",
            "v4",
            name="uq_policy",
            comment="Prevents duplicate policy rules",
        ),
    )
