from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# --- Auth settings ---
class KeyRotation(BaseModel):
    rotation_interval_days: int = 30
    max_historical_keys: int = 5


class BaseSecurity(BaseModel):
    access_token_expire_minutes: int = 60
    allow_weak_passwords: bool = False
    bcrypt_rounds: int = 5
    hash_algorithm: str = "HS256"
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    secret_key: str
    token_audience: str
    token_issuer: str
    key_rotation: KeyRotation


class AuthSettings(BaseModel):
    security: BaseSecurity
    allow_registration: bool = True
    password_min_length: int = 8
    default_user_roles: Union[List[str], str] = ["user"]

    @field_validator("default_user_roles", mode="before")
    def normalize_user_roles(cls, value) -> list:
        """Normalizes user roles to always be a list format.

        Converts single strings to single-element lists and
        handles empty values by returning the default role.
        """
        if value is None:
            return ["user"]
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("default_user_roles")
    def validate_user_roles(cls, value: list) -> list:
        """Validates that roles are non-empty strings.

        Ensures:
        - At least one role is provided
        - All roles are strings
        - Role names are not empty or whitespace-only
        - No duplicate roles in the list
        """
        if not value:
            raise ValueError("At least one default role is required")

        validated_roles = []
        for role in value:
            if not isinstance(role, str):
                raise TypeError("Roles must be strings")

            clean_role = role.strip()
            if not clean_role:
                raise ValueError("Role names cannot be empty or whitespace-only")

            if clean_role not in validated_roles:
                validated_roles.append(clean_role)

        return validated_roles


# --- Token ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: datetime


class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []


# --- Policies settings ---


class PolicyBase(BaseModel):
    ptype: Literal["p", "g"]
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


# --- Role ---
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class Role(RoleBase):
    id: int

    class Config:
        from_attributes = True


class RoleRead(Role):
    pass


class RoleCreate(RoleBase):
    pass


# --- Attribute ---
class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class Group(GroupBase):
    id: int

    class Config:
        from_attributes = True


# --- User Schemas ---
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: str
    is_active: Optional[bool] = True


class UserSelfUpdate(BaseModel):
    """Schema for users updating their own information"""

    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None
    password: Optional[str] = None


class UserAdminUpdate(UserSelfUpdate):
    """Schema for admins updating user information"""

    password: Optional[str] = None
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


# --- Password Management ---
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


# --- Registration ---
class UserRegister(UserCreate):
    terms_accepted: bool = Field(False, description="Must accept terms and conditions")
    captcha: Optional[str] = None

    @model_validator(mode="after")
    def check_terms_accepted(self):
        if not self.terms_accepted:
            raise ValueError("You must accept the terms and conditions")
        return self
