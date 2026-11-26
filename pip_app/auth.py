"""认证：密码校验、会话、失败限速。

设计取舍：
    1. 密码只存在环境变量或本地文件里，用 PBKDF2 派生后比较，不存明文
    2. 会话是内存字典（token → 过期时间），服务重启即失效——单实例服务够用
    3. 暴力破解防护：同一 IP 连续失败 5 次锁 5 分钟
    4. 没配密码时自动生成随机密码并打印到日志（避免"空密码可登录"）

环境变量：
    PIP_USER          默认 admin
    PIP_PASSWORD      不设则自动生成（写入 data/.admin_password 并打印）
    PIP_SESSION_TTL   会话有效期（秒），默认 86400
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import config

USERNAME = os.environ.get("PIP_USER", "admin")
PASSWORD_FILE = config.DATA_DIR / ".admin_password"
SESSION_TTL = int(os.environ.get("PIP_SESSION_TTL", "86400"))

MAX_FAILURES = 5
LOCK_SECONDS = 300

PBKDF2_ROUNDS = 120_000


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)


def _load_or_create_password() -> tuple[str, bool]:
    """返回 (密码, 是否为新生成)。环境变量优先。"""
    env_pwd = os.environ.get("PIP_PASSWORD")
    if env_pwd:
        return env_pwd, False
    if PASSWORD_FILE.exists():
        pwd = PASSWORD_FILE.read_text(encoding="utf-8").strip()
        if pwd:
            return pwd, False
    pwd = secrets.token_urlsafe(12)
    try:
        PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        PASSWORD_FILE.write_text(pwd + "\n", encoding="utf-8")
        try:
            PASSWORD_FILE.chmod(0o600)
        except OSError:
            pass
    except OSError:
        pass
    return pwd, True


_PASSWORD, _GENERATED = _load_or_create_password()
_SALT = b"pip-intel-salt-v1"
_PASSWORD_HASH = _hash(_PASSWORD, _SALT)


def generated_password_notice() -> str:
    if _GENERATED:
        return f"[auth] 已生成初始密码：{_PASSWORD}（可改环境变量 PIP_PASSWORD 覆盖）"
    return ""


def username() -> str:
    return USERNAME


def verify(username_input: str, password_input: str) -> bool:
    """常量时间比较，避免时序侧信道。"""
    if not username_input or not password_input:
        return False
    if not hmac.compare_digest(username_input.strip().lower(), USERNAME.lower()):
        return False
    return hmac.compare_digest(_hash(password_input, _SALT), _PASSWORD_HASH)


# ---------------------------------------------------------------- 会话
@dataclass
class Session:
    user: str
    expires_at: float


@dataclass
class SessionStore:
    ttl: int = SESSION_TTL
    _sessions: dict[str, Session] = field(default_factory=dict)

    def create(self, user: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = Session(user=user, expires_at=time.time() + self.ttl)
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        session = self._sessions.get(token)
        if not session:
            return False
        if session.expires_at < time.time():
            self._sessions.pop(token, None)
            return False
        return True

    def revoke(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)

    def cleanup(self) -> int:
        now = time.time()
        expired = [k for k, v in self._sessions.items() if v.expires_at < now]
        for key in expired:
            self._sessions.pop(key, None)
        return len(expired)


SESSIONS = SessionStore()


# ---------------------------------------------------------------- 限速
@dataclass
class AttemptTracker:
    max_failures: int = MAX_FAILURES
    lock_seconds: int = LOCK_SECONDS
    _state: dict[str, tuple[int, float]] = field(default_factory=dict)

    def locked(self, key: str) -> float:
        """返回剩余锁定秒数，0 表示未锁。"""
        entry = self._state.get(key)
        if not entry:
            return 0.0
        count, until = entry
        if count < self.max_failures:
            return 0.0
        remaining = until - time.time()
        if remaining <= 0:
            self._state.pop(key, None)
            return 0.0
        return remaining

    def fail(self, key: str) -> int:
        count, _until = self._state.get(key, (0, 0.0))
        count += 1
        self._state[key] = (count, time.time() + self.lock_seconds)
        return count

    def success(self, key: str) -> None:
        self._state.pop(key, None)


ATTEMPTS = AttemptTracker()


def cookie_header(token: str, *, max_age: int | None = None) -> str:
    max_age = SESSION_TTL if max_age is None else max_age
    return (
        f"pip_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}"
    )


def clear_cookie_header() -> str:
    return "pip_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


__all__ = [
    "ATTEMPTS", "SESSIONS", "AttemptTracker", "SessionStore",
    "clear_cookie_header", "cookie_header", "generated_password_notice",
    "username", "verify",
]
