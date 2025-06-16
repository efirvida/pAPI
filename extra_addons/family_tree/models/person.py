from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import uuid4

from beanie import Document
from pydantic import UUID4, BaseModel, Field, field_validator, model_validator

AllowedExtraTypes = Union[str, bool, datetime]


class GenderEnum(str, Enum):
    MALE = "M"
    FEMALE = "F"

    @classmethod
    def get_options(cls) -> List[dict]:
        return [
            {"value": member.value, "label": member.name.capitalize()} for member in cls
        ]


class Relations(BaseModel):
    spouses: Optional[List[UUID4]] = None
    children: Optional[List[UUID4]] = None
    father: Optional[UUID4] = None
    mother: Optional[UUID4] = None


class PersonalData(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[GenderEnum] = Field(
        default=GenderEnum.MALE, description="Person's gender"
    )
    birth_date: Optional[date] = Field(
        default=None, description="Date of birth in YYYY-MM-DD format"
    )
    description: Optional[str] = None

    @field_validator("birth_date", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

    model_config = {
        "populate_by_name": True,
        "extra": "allow",
    }


class BasePerson(BaseModel):
    rels: Optional[Relations] = None
    data: PersonalData

    @model_validator(mode="before")
    @classmethod
    def default_empty_rels(cls, values):
        if "rels" not in values or values["rels"] is None:
            values["rels"] = {}
        return values

    model_config = {
        "from_attributes": True,
    }


class PersonDocument(BasePerson, Document):
    id: UUID4 = Field(default_factory=uuid4, alias="_id")

    class Settings:
        name = "people"
