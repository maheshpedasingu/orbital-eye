from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="ORBITAL-EYE API", version="0.1.0")


@app.get("/api/health")
def health():
    """Basic health check. Returns the server time in UTC."""
    return {
        "status": "ok",
        "service": "orbital-eye-backend",
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }
