from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, EmailStr, Field, field_validator

from user_auth_system.security.user import validate_username

from .group import Group
from .role import Role


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: str
    is_active: Optional[bool] = True

    @field_validator("username", mode="before")
    def check_username(cls, v):
        return validate_username(v)


class UserUpdateBase(BaseModel):
    """Base class for user update operations.
    
    Contains common fields that can be updated by users.
    """
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None
    password: Optional[str] = None


class UserSelfUpdate(UserUpdateBase):
    """Schema for users updating their own information."""
    pass


class UserAdminUpdate(UserUpdateBase):
    """Schema for administrators updating user information.
    
    Extends UserUpdateBase with additional fields that only admins can modify.
    """
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    roles: Optional[List[int]] = None
    groups: Optional[List[int]] = None


class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    roles: List[Role] = []
    groups: List[Group] = []

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    id: int
    hashed_password: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    roles: List[Role] = []
    groups: List[Group] = []

    class Config:
        from_attributes = True

    @property
    def casbin_roles(self) -> List[Tuple[str, str, str]]:
        """
        Returns the Casbin 'g' grouping policies for this user.
        Format: [("g", "username", "role:role_name"), ("g", "username", "group:group_name")]
        """
        username = self.username
        links = []

        for role in self.roles:
            links.append(("g", username, f"role:{role.name}"))

        for group in self.groups:
            links.append(("g", username, f"group:{group.name}"))

        return links


class UserPublic(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    is_superuser: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: List[str] = []
    groups: List[str] = []

    class Config:
        from_attributes = True


class UserDetailResponse(UserPublic):
    is_superuser: bool
    last_login: Optional[datetime] = None


class UsersListResponse(BaseModel):
    users: List[UserPublic]
    total: int
    page: int
    per_page: int
