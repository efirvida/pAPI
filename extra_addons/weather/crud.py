import requests


def get_weather(latitude: float, longitude: float) -> dict:
    """
    Fetch current weather data using the Open-Meteo API (no API key required).

    Args:
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.

    Returns:
        dict: Dictionary with temperature (°C), windspeed (km/h), and humidity (%),
              or error information if request fails.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,wind_speed_10m,relative_humidity_2m"
    )

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raises HTTPError for bad status codes
        data = response.json()

        current = data.get("current")
        if not current:
            raise ValueError("Missing 'current' field in API response")

        return {
            "temperature": current["temperature_2m"],
            "windspeed": current["wind_speed_10m"],
            "humidity": current["relative_humidity_2m"],
        }

    except Exception as e:
        return {
            "temperature": None,
            "windspeed": None,
            "humidity": None,
            "error": str(e),
        }
