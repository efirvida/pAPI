from typing import Literal

from pydantic import BaseModel


class PolicyBase(BaseModel):
    ptype: Literal["p"] = "p"
    subject: str
    object: str
    action: str
    condition: str
    effect: str

    @property
    def policy(self):
        return (
            self.ptype,
            self.subject,
            self.object,
            self.action,
            self.condition,
            self.effect,
        )


class PolicyCreate(PolicyBase):
    pass


class PolicyRead(PolicyBase):
    pass


class PolicyInDB(PolicyBase):
    id: int

    class Config:
        from_attributes = True


class PolicyRole(BaseModel):
    username: set
    role: str


class PolicyRoleCreate(PolicyRole):
    pass


class PolicyRoleRead(PolicyRole):
    pass


class PolicyRoleInDB(PolicyRole):
    id: int

    class Config:
        from_attributes = True
