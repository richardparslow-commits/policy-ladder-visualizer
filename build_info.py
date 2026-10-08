"""Public source fingerprint for proving which deployment the canary tested."""
from hashlib import sha256
from pathlib import Path


def app_revision():
    root = Path(__file__).resolve().parent
    digest = sha256()
    for name in ("streamlit_app.py", "model.py", "pdf_report.py", "requirements.txt", ".streamlit/config.toml"):
        digest.update(name.encode()); digest.update((root / name).read_bytes())
    return digest.hexdigest()[:16]


if __name__ == "__main__":
    print(app_revision())
