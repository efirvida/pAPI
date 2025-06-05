from pydantic import Field, model_validator

from .user import UserCreate


class UserRegister(UserCreate):
    """Schema for user registration with terms acceptance.

    Extends UserCreate to add terms and conditions acceptance requirement.
    """

    terms_accepted: bool = Field(False, description="Must accept terms and conditions")

    @model_validator(mode="after")
    def check_terms_accepted(self):
        """Validates that terms and conditions have been accepted."""
        if not self.terms_accepted:
            raise ValueError("You must accept the terms and conditions")
        return self
