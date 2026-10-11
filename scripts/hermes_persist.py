#!/usr/bin/env python3
"""Encrypted, versioned GitHub Actions snapshots for the ephemeral Hermes runner.

Only ciphertext may leave the runner. NEVER commit plaintext state or the
dashboard password. The public repo's artifacts are readable by other users.
"""
from __future__ import annotations
import argparse
import io
import os
from pathlib import Path, PurePosixPath
import secrets
import sqlite3
import sys
import tempfile
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC = b"HERMES_BACKUP_V1\x00"
AAD = b"hermes-github-public-artifact-2026-v1"
ITERATIONS = 600_000
MAX_FILE = 25 * 1024 * 1024
MAX_TOTAL = 65 * 1024 * 1024

# DO NOT archive installer binaries, Ollama models, tokens, or Hermes .env.
HERME_FILES = ("config.yaml", "SOUL.md", "USER.md", "AGENTS.md", "state.db")
HERME_DIRS = ("memories", "sessions", "skills", "cron", "hooks", "plugins", "profiles", "notes", "knowledge")
IGNORE_NAMES = {".env", ".git", ".ssh", ".aws", ".azure", ".gnupg", ".npmrc", "id_rsa",
                "id_ed25519", "credentials.json", "auth.json", "token.json",
                "state.db-wal", "state.db-shm", "__pycache__", "node_modules", ".venv"}


def password() -> bytes:
    # This value is a repository Actions secret; it never appears in logs or files.
    pw = os.getenv("HERMES_DASHBOARD_PASSWORD", "")
    if len(pw) < 14:
        raise ValueError("HERMES_DASHBOARD_PASSWORD must be at least 14 characters")
    return pw.encode("utf-8")


def derive(pw: bytes, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                      salt=salt, iterations=ITERATIONS).derive(pw)


def allowed(path: Path) -> bool:
    return not any(part.lower() in IGNORE_NAMES for part in path.parts)


def iter_files(home: Path, workspace: Path):
    for filename in HERME_FILES:
        p = home / filename
        if p.is_file() and not p.is_symlink():
            yield "hermes/" + filename, p
    for folder in HERME_DIRS:
        root = home / folder
        if not root.is_dir() or root.is_symlink():
            continue
        for p in root.rglob("*"):
            if p.is_file() and not p.is_symlink():
                rel = p.relative_to(home)
                if allowed(rel):
                    yield "hermes/" + rel.as_posix(), p
    if workspace.is_dir():
        for p in workspace.rglob("*"):
            if p.is_file() and not p.is_symlink():
                rel = p.relative_to(workspace)
                if allowed(rel):
                    yield "workspace/" + rel.as_posix(), p


def sqlite_bytes(path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "snapshot.db"
        # SQLite online backup is WAL-safe even while Hermes is running.
        with sqlite3.connect("file:" + path.as_posix() + "?mode=ro", uri=True, timeout=30) as src:
            with sqlite3.connect(str(target)) as dst:
                src.backup(dst, pages=100, sleep=0.2)
        return target.read_bytes()


def save(home: Path, workspace: Path, destination: Path, pw: bytes):
    seen = set()
    total = 0
    files = 0
    plain = io.BytesIO()
    with zipfile.ZipFile(plain, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, path in iter_files(home, workspace):
            if name in seen:
                raise ValueError("Duplicate archive path: " + name)
            seen.add(name)
            if path.name == "state.db":
                data = sqlite_bytes(path)
            else:
                size = path.stat().st_size
                if size > MAX_FILE:
                    raise ValueError("File too large for automatic backup: " + name)
                data = path.read_bytes()
            if len(data) > MAX_FILE:
                raise ValueError("File too large for automatic backup: " + name)
            total += len(data)
            if total > MAX_TOTAL:
                raise ValueError("Hermes user data exceeds backup limit; export externally")
            z.writestr(name, data)
            files += 1
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    ciphertext = AESGCM(derive(pw, salt)).encrypt(nonce, plain.getvalue(), AAD)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(MAGIC + salt + nonce + ciphertext)
    print(f"Encrypted Hermes snapshot: {files} files, {total} bytes plaintext; {destination.stat().st_size} bytes encrypted.")
    # Keep only encrypted output on disk. plaintext was in memory.


def restore(home: Path, workspace: Path, source: Path, pw: bytes):
    payload = source.read_bytes()
    if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 16 + 12 + 16:
        raise ValueError("Unrecognized or truncated Hermes encrypted backup")
    offset = len(MAGIC)
    salt = payload[offset:offset+16]
    nonce = payload[offset+16:offset+28]
    plain = AESGCM(derive(pw, salt)).decrypt(nonce, payload[offset+28:], AAD)
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        files = z.infolist()
        if sum(x.file_size for x in files) > MAX_TOTAL or len(files) > 10_000:
            raise ValueError("Backup limits exceeded")
        for entry in files:
            p = PurePosixPath(entry.filename)
            if (entry.is_dir() or len(p.parts) < 2 or p.parts[0] not in ("hermes", "workspace") or
                p.is_absolute() or ".." in p.parts or not allowed(Path(*p.parts[1:]))):
                raise ValueError("Unsafe file path in encrypted backup: " + entry.filename)
            target_root = home if p.parts[0] == "hermes" else workspace
            target = target_root.joinpath(*p.parts[1:])
            if target.is_symlink():
                raise ValueError("Refusing to overwrite symlink: " + entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Do not overwrite an installed executable: only files inside curated
            # Hermes directories or the separate agent workspace were saved.
            data = z.read(entry)
            if len(data) != entry.file_size or len(data) > MAX_FILE:
                raise ValueError("Invalid backup file size: " + entry.filename)
            target.write_bytes(data)
    print(f"Restored {len(files)} files from encrypted Hermes snapshot.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=("save", "restore", "selftest"))
    p.add_argument("--home", type=Path)
    p.add_argument("--workspace", type=Path)
    p.add_argument("--file", type=Path)
    args = p.parse_args()
    if args.operation == "selftest":
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home, work = root / "home", root / "work"
            home.mkdir()
            (home / "memories").mkdir()
            (home / "memories" / "test.md").write_text("Memory survives a runner restart.")
            (home / ".env").write_text("SECRET_NOT_IN_ARCHIVE")
            work.mkdir()
            (work / "hello.py").write_text("print('hello')")
            with sqlite3.connect(home / "state.db") as db:
                db.execute("CREATE TABLE sessions (value TEXT)")
                db.execute("INSERT INTO sessions VALUES ('persisted')")
            pw = b"test-value-only-not-a-real-password"
            backup = root / "encrypted.bin"
            save(home, work, backup, pw)
            assert b"SECRET_NOT_IN_ARCHIVE" not in backup.read_bytes()
            assert b"Memory survives" not in backup.read_bytes()
            (home / "memories" / "test.md").unlink()
            (home / "state.db").unlink()
            (work / "hello.py").unlink()
            restore(home, work, backup, pw)
            assert (home / "memories" / "test.md").read_text() == "Memory survives a runner restart."
            assert (work / "hello.py").read_text() == "print('hello')"
            with sqlite3.connect(home / "state.db") as db:
                assert db.execute("SELECT value FROM sessions").fetchone()[0] == "persisted"
            try:
                restore(home, work, backup, b"wrong-password-value")
                raise AssertionError("Wrong password should fail")
            except Exception as exc:
                from cryptography.exceptions import InvalidTag
                if not isinstance(exc, InvalidTag):
                    raise
            print("Encrypted state round-trip, SQLite and password verification passed.")
        return
    if not args.home or not args.workspace or not args.file:
        p.error("Must provide --home, --workspace and --file")
    if args.operation == "save":
        save(args.home, args.workspace, args.file, password())
    else:
        restore(args.home, args.workspace, args.file, password())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"State {sys.argv[1] if len(sys.argv)>1 else 'operation'} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
