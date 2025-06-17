from typing import Optional

from pydantic import BaseModel


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class Role(RoleBase):
    id: int

    class Config:
        from_attributes = True


class RoleCreate(RoleBase):
    pass


class RoleRead(Role):
    pass
