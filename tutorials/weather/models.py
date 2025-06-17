from datetime import datetime, timezone

from beanie import Document, PydanticObjectId, BeanieObjectId
from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float


class WeatherStation(Document):
    name: str
    location: Location
    created_at: datetime = Field(
        default_factory=lambda d: datetime.now(tz=timezone.utc)
    )

    class Settings:
        name = "weather_stations"  # MongoDB collection name


class WeatherReading(Document):
    station_id: PydanticObjectId
    temperature: float
    windspeed: float
    humidity: float
    timestamp: datetime = Field(default_factory=lambda d: datetime.now(tz=timezone.utc))

    class Settings:
        name = "weather_readings"
