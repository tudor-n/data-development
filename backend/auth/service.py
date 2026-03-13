"""
Auth service — password hashing, JWT access + refresh tokens.
Drop-in for any deployment: tokens are stateless, refresh tokens are revocable.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt


from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import RefreshToken, User

# ─── Config ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))



# ─── Password utils ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")



def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT ─────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises JWTError on invalid/expired tokens."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Token type mismatch")
    return payload


# ─── Refresh tokens ──────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    """Store only the SHA-256 hash, not the raw token value."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(
    db: AsyncSession,
    user_id: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    raw = secrets.token_urlsafe(64)
    token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(token)
    await db.flush()
    return raw  # return raw once; never stored in plaintext


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, "User"]:
    """
    Validate old token, revoke it, issue a new one.
    Returns (new_raw_token, user).
    Raises ValueError on invalid/expired/revoked token.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise ValueError("Token not found")
    if token.revoked:
        # Possible token theft — revoke all tokens for this user
        await _revoke_all_user_tokens(db, token.user_id)
        raise ValueError("Token already used (possible token reuse attack)")
    if token.expires_at < datetime.now(timezone.utc):
        raise ValueError("Token expired")

    token.revoked = True
    await db.flush()

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ValueError("User not found or inactive")

    new_raw = await create_refresh_token(db, user.id, user_agent, ip_address)
    return new_raw, user


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token:
        token.revoked = True
        await db.flush()


async def _revoke_all_user_tokens(db: AsyncSession, user_id: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False  # noqa: E712
        )
    )
    for token in result.scalars().all():
        token.revoked = True
    await db.flush()


# ─── User CRUD ───────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
