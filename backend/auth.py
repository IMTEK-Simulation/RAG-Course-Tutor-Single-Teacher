from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request

from .config import AUTH_FILE, SECRET_FILE

SESSION_SECONDS = 12 * 60 * 60


class SingleAccountAuth:
    def __init__(self, account_file: Path = AUTH_FILE, secret_file: Path = SECRET_FILE) -> None:
        self.account_file = account_file
        self.secret_file = secret_file
        self.account_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return self.account_file.exists()

    def setup(self, username: str, password: str) -> None:
        if self.configured:
            raise HTTPException(status_code=409, detail="Das Dozentenkonto ist bereits eingerichtet.")
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        payload = {
            "version": 1,
            "username": username,
            "salt": base64.b64encode(salt).decode(),
            "password_hash": base64.b64encode(digest).decode(),
        }
        try:
            descriptor = os.open(self.account_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail="Das Dozentenkonto ist bereits eingerichtet.") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def verify(self, username: str, password: str) -> bool:
        if not self.configured:
            return False
        payload = json.loads(self.account_file.read_text(encoding="utf-8"))
        salt = base64.b64decode(payload["salt"])
        expected = base64.b64decode(payload["password_hash"])
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(payload["username"], username) and hmac.compare_digest(expected, actual)

    def _secret(self) -> bytes:
        if not self.secret_file.exists():
            self.secret_file.write_bytes(os.urandom(32))
            os.chmod(self.secret_file, 0o600)
        return self.secret_file.read_bytes()

    def issue_token(self, username: str) -> str:
        payload = f"{username}|{int(time.time()) + SESSION_SECONDS}"
        signature = hmac.new(self._secret(), payload.encode(), hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()

    def token_username(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            username, expires, signature = decoded.rsplit("|", 2)
            payload = f"{username}|{expires}"
            expected = hmac.new(self._secret(), payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected) or int(expires) < int(time.time()):
                return None
            return username
        except (ValueError, UnicodeDecodeError):
            return None

    def require(self, request: Request) -> str:
        username = self.token_username(request.cookies.get("rag_tutor_session"))
        if username is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
        return username
