from app.config import load_env
from app.ingestion.firms import redact


def test_load_env_reads_bom_file_and_skips_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("DEMO_VALUE", raising=False)
    f = tmp_path / ".env"
    f.write_bytes("\ufeff# comment\nDEMO_VALUE=abc123\n".encode("utf-8"))
    load_env(f)
    import os
    assert os.environ["DEMO_VALUE"] == "abc123"


def test_redact_removes_the_key():
    assert "SECRET" not in redact("GET /csv/SECRET/VIIRS failed", "SECRET")
