"""
安全工具：密码哈希 + JWT 签发/验签。

密码哈希使用标准库 pbkdf2_hmac（零第三方依赖），
JWT 使用 PyJWT (HS256)，密钥与过期时间来自 Settings。
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets

import jwt
from loguru import logger

from app.core.config import settings

# PBKDF2 参数（OWASP 建议 600k 次迭代，本地开发 200k 已够）
_PBKDF2_ITERATIONS: int = 200_000
_PBKDF2_ALGO: str = "sha256"


def hash_password(password: str) -> str:
    """生成密码哈希，格式: pbkdf2$sha256$iterations$salt_hex$hash_hex。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return (
        f"pbkdf2${_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, hashed: str) -> bool:
    """校验密码。哈希格式不符时返回 False（不抛异常）。"""
    try:
        _, algo, iterations, salt_hex, hash_hex = hashed.split("$")
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            algo, password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    username: str,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT 访问令牌。"""
    expire_minutes = expires_minutes or settings.jwt_expire_minutes
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(subject),
        "role": role,
        "username": username,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    """验签并解析 JWT；无效或过期返回 None。"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        logger.bind(component="security").warning("Token decode failed: {}", exc)
        return None


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
]