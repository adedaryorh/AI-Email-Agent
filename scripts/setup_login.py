"""Set the single-user browser password; never prints or stores the plaintext."""
import getpass
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.passwords import hash_password  # noqa: E402

path = Path(".env")
if not path.exists():
    raise SystemExit("Run scripts/init_env.py first")
username = input("Browser username [admin]: ").strip() or "admin"
if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,100}", username):
    raise SystemExit("Use letters, numbers, _, ., @ or - in the username")
password = getpass.getpass("Password (at least 12 characters): ")
if len(password) < 12 or password != getpass.getpass("Confirm password: "):
    raise SystemExit("Password too short or confirmation did not match")
values = {"BROWSER_USERNAME": username, "BROWSER_PASSWORD_HASH": hash_password(password)}
lines = [line for line in path.read_text().splitlines() if line.split("=", 1)[0] not in values]
path.write_text("\n".join(lines + [f"{k}={v}" for k,v in values.items()]) + "\n")
path.chmod(0o600)
print("Browser login configured. Restart the API. Previous sessions will expire.")
