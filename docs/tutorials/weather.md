## 🌦️ Weather Addon Example

This addon demonstrates how to build a basic weather data API using **pAPI**, with persistent storage in MongoDB via the integrated **Beanie** ODM.

Through this example, you will learn how to:

* Integrate MongoDB using **Beanie**
* Add Python dependencies to your addon
* Register and list weather stations
* Fetch real-time weather data from an external API

> 💡 **Bonus**: Learn how to interact with MongoDB using the integrated shell.

---

### 🗂️ Project Structure

```
my_addons/
└── weather/
    ├── __init__.py
    ├── manifest.yaml
    ├── models.py
    ├── crud.py
    └── routers.py
```

---

### 📄 `manifest.yaml`

Declares the addon and its required dependencies:

```yaml
name: weather
version: 1.0.0
description: Weather data API
author: Your Name

python_dependencies:
  - "requests>=2.28.0"
```

---

### 🧬 `models.py`

Defines the database models for weather stations and readings:

```python
from datetime import datetime, timezone
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float


class WeatherStation(Document):
    name: str
    location: Location
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    class Settings:
        name = "weather_stations"


class WeatherReading(Document):
    station_id: PydanticObjectId
    temperature: float
    windspeed: float
    humidity: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    class Settings:
        name = "weather_readings"
```

---

### 🔌 `routers.py`

Handles the REST API endpoints:

```python
from fastapi import HTTPException
from papi.core.response import create_response
from papi.core.router import RESTRouter

from .crud import get_weather
from .models import WeatherReading, WeatherStation

router = RESTRouter()


@router.get("/stations")
async def list_stations():
    """List all registered weather stations."""
    stations = await WeatherStation.find_all().to_list()
    return create_response(data=stations)


@router.post("/stations")
async def create_station(station: WeatherStation):
    """Register a new weather station."""
    await station.create()
    return create_response(message="Station created successfully", data=station)


@router.get("/stations/{station_id}/weather")
async def get_current_weather_for_station(station_id: str):
    """
    Fetch the current weather data for a given station.
    Also saves the reading to the database.
    """
    station = await WeatherStation.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    weather = get_weather(station.location.latitude, station.location.longitude)

    await WeatherReading(station_id=station.id, **weather).save()

    return create_response(data=weather)
```

---

### 🌐 `crud.py`

Fetches weather data using the Open-Meteo public API:

```python
import requests

def get_weather(latitude: float, longitude: float) -> dict:
    """
    Fetch current weather data using the Open-Meteo API (no API key required).
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,wind_speed_10m,relative_humidity_2m"
    )

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        current = data.get("current")
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

### 📦 `__init__.py`

This file registers your addon so it can be discovered and loaded by **pAPI**.

It also registers the **Beanie documents** so they are initialized with the MongoDB connection during pAPI startup.

```python
from .models import WeatherReading, WeatherStation
from .router import router

# Register the API router and Beanie documents for MongoDB
__all__ = [
    "router",              # Registers the API routes
    "WeatherStation",      # Registers the weather station document
    "WeatherReading"       # Registers the weather reading document
]
```

---

### ⚙️ Configuration (`config.yaml`)

```yaml

# base configuration check the hello world example
... 

# MongoDB connection settings
database:
  mongodb_uri: "mongodb://root:example@localhost:27017/weather_db?authSource=admin"

# Enable the weather addon
addons:
  extra_addons_path: "my_addons"
  enabled:
    - weather
```

---

## 🧪 How to Use

### 🚀 Start the API Server

```bash
rye run python papi/cli.py webserver
```

---

### 📍 Create a Weather Station

```bash
curl -X 'POST' \
  'http://localhost:8080/stations' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Santa Clara, Cuba",
  "location": {
    "latitude": 22.4067,
    "longitude": -79.9531
  }
}'
```

#### ✅ Example Response

```json
{
  "success": true,
  "message": "Station created successfully",
  "data": {
    "_id": "684da177ebcda212e2ce8dac",
    "name": "Santa Clara, Cuba",
    "location": {
      "latitude": 22.4067,
      "longitude": -79.9531
    },
    "created_at": "2025-06-14T16:21:11.352782Z"
  },
  "error": null,
  "meta": { ... }
}
```

---

### 📋 List All Stations

```bash
curl -X 'GET' \
  'http://localhost:8080/stations' \
  -H 'accept: application/json'
```

#### ✅ Example Response
```json
{
  "success": true,
  "message": null,
  "data": [
    {
      "_id": "684daa34dc94122d9d84bac9",
      "name": "Santa Clara, Cuba",
      "location": {
        "latitude": 22.4067,
        "longitude": -79.9531
      },
      "created_at": "2025-06-14T16:58:28.540000"
    }
  ],
  "error": null,
  "meta": {
    "timestamp": "2025-06-14T17:17:01+00:00Z",
    "requestId": "888ecf22-ea67-4f37-87e1-c13d6f32cfea"
  }
}
```

---

### 🌡️ Get Weather for a Station

```bash
curl -X 'GET' \
  'http://localhost:8080/stations/684da177ebcda212e2ce8dac/weather' \
  -H 'accept: application/json' 
```

#### ✅ Example Response

```json
{
  "success": true,
  "message": null,
  "data": {
    "temperature": 31.2,
    "windspeed": 18.7,
    "humidity": 56
  },
  "error": null,
  "meta": { ... }
}
```

---

## 🛠️ MongoDB Shell Access (via pAPI Shell)

Access the MongoDB shell:

```bash
rye run python papi/cli.py shell
```

### 🔍 Available Documents

```python
In [1]: mongo_documents
Out[1]:
{
  'WeatherStation': weather.models.WeatherStation,
  'WeatherReading': weather.models.WeatherReading
}
```

### 🧾 List Stations in Shell

```python
In [2]: await mongo_documents["WeatherStation"].find().to_list()
```

### ✏️ Rename a Station

```python
In [3]: from beanie import BeanieObjectId as ObjectId
In [4]: station = await mongo_documents["WeatherStation"].get(ObjectId('684daa34dc94122d9d84bac9'))
In [5]: station.name = "New Santa Clara"
In [6]: await station.save()
```

Confirm the change:

```python
In [7]: await mongo_documents["WeatherStation"].get(ObjectId('684daa34dc94122d9d84bac9'))
Out[7]: WeatherStation(name='New Santa Clara', ...)
```
