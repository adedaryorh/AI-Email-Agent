"""Generate a local development environment without printing credentials."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet

path = Path(".env")
values = {"API_KEY": secrets.token_urlsafe(32), "SECRET_KEY": secrets.token_urlsafe(32), "ENCRYPTION_KEY": Fernet.generate_key().decode()}
source = Path(".env.example").read_text()
for key, value in values.items():
    source = source.replace(f"{key}=\n", f"{key}={value}\n")
with path.open("x") as stream:
    stream.write(source)
path.chmod(0o600)
print("Created .env; add Google OAuth and LLM credentials before running.")
