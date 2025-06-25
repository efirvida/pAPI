# 🌦️ Weather Addon Example (SQLAlchemy Version)

This addon showcases how to build a basic weather data API using **pAPI**, now powered by **SQLAlchemy** for persistent storage.

With this example, you will learn how to:

* Integrate an SQL database using SQLAlchemy's async engine
* Declare and manage Python dependencies within your addon
* Register and list weather stations
* Retrieve and save real-time weather data from an external API

---

### 🗂️ Project Structure

```
my_addons/
└── weather/
    ├── __init__.py
    ├── manifest.yaml
    ├── models.py
    ├── schemas.py
    ├── crud.py
    └── routers.py
```

---

### 📄 `manifest.yaml`

Defines the addon metadata and required Python packages:

```yaml
name: weather
version: 1.0.0
description: Weather data API (SQLAlchemy version)
author: Your Name

python_dependencies:
  - "requests>=2.28.0"
```

---

### 🧬 `models.py`

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class WeatherStation(Base):
    __tablename__ = "weather_stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    readings = relationship("WeatherReading", back_populates="station")


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("weather_stations.id"))
    temperature = Column(Float)
    windspeed = Column(Float)
    humidity = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    station = relationship("WeatherStation", back_populates="readings")
```

---

### 📊 `schemas.py`

```python
from datetime import datetime
from pydantic import BaseModel

class WeatherStationBase(BaseModel):
    name: str
    latitude: float
    longitude: float

class WeatherStationCreate(WeatherStationBase):
    pass

class WeatherStationOut(WeatherStationBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class WeatherReadingOut(BaseModel):
    id: int
    station_id: int
    temperature: float | None
    windspeed: float | None
    humidity: float | None
    timestamp: datetime

    class Config:
        orm_mode = True
```

---

### 🌐 `crud.py`

```python
import requests

def get_weather(latitude: float, longitude: float) -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,wind_speed_10m,relative_humidity_2m"
    )

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        current = response.json().get("current")
        if not current:
            raise ValueError("Missing 'current' field in API response")

        return {
            "temperature": current["temperature_2m"],
            "windspeed": current["wind_speed_10m"],
            "humidity": current["relative_humidity_2m"]
        }

    except Exception as e:
        return {
            "temperature": None,
            "windspeed": None,
            "humidity": None,
            "error": str(e)
        }
```

---


### 🔌 `routers.py`

pAPI provides the `sql_session` dependency, which you can use directly as a router dependency in your route functions. Alternatively, you can use the asynchronous context manager `get_sql_session` that yields a SQLAlchemy session within an async context.

---

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from papi.core.db import sql_session, get_sql_session
from papi.core.router import RESTRouter

from . import models, schemas
from .crud import get_weather

router = RESTRouter()


@router.post("/stations", response_model=schemas.WeatherStationOut)
async def create_station(
    station: schemas.WeatherStationCreate, db: AsyncSession = Depends(sql_session)
):
    new_station = models.WeatherStation(
        name=station.name, latitude=station.latitude, longitude=station.longitude
    )
    db.add(new_station)
    await db.commit()
    await db.refresh(new_station)
    return new_station


@router.get("/stations", response_model=list[schemas.WeatherStationOut])
async def list_stations(db: AsyncSession = Depends(sql_session)):
    result = await db.execute(select(models.WeatherStation))
    return result.scalars().all()


@router.get("/stations/{station_id}/weather", response_model=schemas.WeatherReadingOut)
async def get_current_weather(station_id: int):
    # Using get_sql_session context here
    async with get_sql_session() as session:
        result = await session.execute(
            select(models.WeatherStation).where(models.WeatherStation.id == station_id)
        )
        station = result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        weather = get_weather(station.latitude, station.longitude)
        reading = models.WeatherReading(
            station_id=station.id,
            temperature=weather["temperature"],
            windspeed=weather["windspeed"],
            humidity=weather["humidity"],
        )
        session.add(reading)
        await session.commit()
        await session.refresh(reading)
        return reading
```

---

### 📆 `__init__.py`

```python
from . import models, routers

__all__ = ["router","models"]
```

---

### ⚙️ Main papi configuration (`config.yaml`)

```yaml
# Base configuration – see the Hello World example
...

# SQLAlchemy connection settings (example using SQLite)
database:
  sqlalchemy_uri: "sqlite+aiosqlite:///./weather.db"
  backends:
    sqlalchemy:
      echo: false  # Optional: enables SQL query logging

# Enable the weather addon
addons:
  extra_addons_path: "my_addons"
  enabled:
    - weather
```

pAPI allows fine-tuning of the database engine by providing additional configuration under the `backends` section in `config.yaml`.

---

## 🚜 How to Use

### 🚀 Start the API Server

```bash
rye run python papi/cli.py webserver
```
Once the pAPI server is started, the system will automatically detect the SQLAlchemy models and route definitions, initialize the corresponding database tables, and register the API endpoints with the main FastAPI application.

**Add a station:**

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/stations' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Santa Clara, Cuba",
  "latitude": 22.4067,
  "longitude": -79.9531
}'
```

**Response:**

```json
{
  "id": 1,
  "name": "Santa Clara, Cuba",
  "latitude": 22.4067,
  "longitude": -79.9531,
  "created_at": "2025-06-25T14:00:14.162273"
}
```

---

**List all stations:**

```bash
curl -X 'GET' \
  'http://localhost:8080/stations' \
  -H 'accept: application/json'
```

**Response:**

```json
[
  {
    "id": 1,
    "name": "Santa Clara, Cuba",
    "latitude": 22.4067,
    "longitude": -79.9531,
    "created_at": "2025-06-25T14:00:14.162273"
  }
]
```

---

**Get weather data for station 1:**

```bash
curl -X 'GET' \
  'http://localhost:8000/stations/1/weather' \
  -H 'accept: application/json'
```

**Response:**

```json
{
  "id": 1,
  "station_id": 1,
  "temperature": 28.3,
  "windspeed": 15.4,
  "humidity": 71.0,
  "timestamp": "2025-06-25T14:05:48.300713"
}
```
