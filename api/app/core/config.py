"""Application settings."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    labledger_data_dir: Path = Path("data")
    bind_host: str = "127.0.0.1"
    app_passphrase: str | None = None
    # Cookie signing key. Unset -> generated once and persisted in the data dir.
    session_secret: str | None = None
    # Force the Secure cookie flag on/off. Unset -> on whenever the request is HTTPS.
    cookie_secure: bool | None = None
    extractor_plugin: str | None = None
    database_url: str | None = None
    ocr_engine: str = "tesseract"
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MiB per file
    backup_keep: int = 14
    job_poll_interval_sec: float = 0.5

    @field_validator("cookie_secure", "session_secret", "app_passphrase", mode="before")
    @classmethod
    def _blank_is_unset(cls, v):
        # docker-compose passes unset vars through as ""
        return None if isinstance(v, str) and not v.strip() else v

    @property
    def db_path(self) -> Path:
        return self.labledger_data_dir / "labledger.db"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.db_path}"

    @property
    def files_dir(self) -> Path:
        return self.labledger_data_dir / "files"

    @property
    def backups_dir(self) -> Path:
        return self.labledger_data_dir / "backups"

    def signing_key(self) -> str:
        """SESSION_SECRET if set, else a random key persisted at <data_dir>/.session_secret."""
        if self.session_secret:
            return self.session_secret
        f = self.labledger_data_dir / ".session_secret"
        try:
            return f.read_text().strip() or self._new_key(f)
        except FileNotFoundError:
            return self._new_key(f)

    @staticmethod
    def _new_key(f: Path) -> str:
        key = secrets.token_hex(32)
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)
        return key

    @property
    def passphrase_enabled(self) -> bool:
        return bool(self.app_passphrase)


settings = Settings()
