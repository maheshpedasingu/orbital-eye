import httpx

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"


def redact(text: str, key: str) -> str:
    """Remove the secret key from any text before it is shown or logged."""
    return text.replace(key, "***")


def check_data_availability(key: str, sensor: str = "VIIRS_SNPP_NRT") -> str:
    """Ask FIRMS which dates are available for a sensor. Returns CSV text.

    Raises RuntimeError (with the key redacted) on any failure.
    """
    url = f"{BASE_URL}/data_availability/csv/{key}/{sensor}"
    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        raise RuntimeError(redact(f"FIRMS request failed: {exc}", key)) from None
