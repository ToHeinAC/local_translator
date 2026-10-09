"""Local user store with bcrypt hashes in ``<data_dir>/users.json`` (the only auth I/O)."""

import json
from collections.abc import Mapping
from pathlib import Path

import bcrypt

#: username -> environment variable holding that account's seed password.
SEED_USERS = {"T. Hein": "SEED_PW_HEIN", "Gast": "SEED_PW_GAST"}


def _file(data_dir: Path) -> Path:
    return data_dir / "users.json"


def ensure_seeded(data_dir: Path, env: Mapping[str, str]) -> None:
    """Create ``users.json`` from the seed passwords once; an existing file is never touched."""
    if _file(data_dir).exists():
        return
    users = {u: env[var] for u, var in SEED_USERS.items() if env.get(var)}
    if not users:
        raise RuntimeError("Keine Start-Passwörter: " + " / ".join(SEED_USERS.values()))
    hashed = {
        u: {"pw_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()}
        for u, pw in users.items()
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    _file(data_dir).write_text(json.dumps({"users": hashed}, indent=2, ensure_ascii=False))


def verify(data_dir: Path, username: str, password: str) -> bool:
    """True if the user exists and the password matches; any read or hash error denies."""
    try:
        stored = json.loads(_file(data_dir).read_text())["users"][username]["pw_hash"]
        return bcrypt.checkpw(password.encode(), stored.encode())
    except (OSError, ValueError, KeyError, TypeError):
        return False
