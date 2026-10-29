import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (never overrides)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def get_firms_key() -> str | None:
    """The FIRMS MAP_KEY from the environment, or None if not configured."""
    load_env()
    return os.environ.get("FIRMS_MAP_KEY") or None
