from fastapi import HTTPException

from papi.core.response import create_response
from papi.core.router import RESTRouter

from .crud import get_weather
from .models import WeatherReading, WeatherStation

router = RESTRouter()


@router.get("/stations")
async def list_stations():
    """
    List all weather stations.
    """
    stations = await WeatherStation.find_all().to_list()
    return create_response(data=stations)


@router.post("/stations")
async def create_station(station: WeatherStation):
    """
    Create a new weather station.
    """
    await station.create()
    return create_response(message="Station created successfully", data=station)


@router.get("/stations/{station_id}/weather")
async def get_current_weather_for_station(station_id: str):
    """
    Fetch current weather data for a specific station.
    Saves a reading and returns the data.
    """
    station = await WeatherStation.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    weather = get_weather(station.location.latitude, station.location.longitude)

    # Store the weather reading
    await WeatherReading(station_id=station.id, **weather).save()

    return create_response(data=weather)
