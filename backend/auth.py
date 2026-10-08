import os
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from database import get_db

LOCAL_DEVELOPMENT_IDENTITY = ("local-development", "local@localhost")


def _auth_mode() -> str:
    mode = os.getenv("AUTH_MODE", "cloudflare").strip().lower()
    if mode not in {"cloudflare", "development"}:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AUTH_MODE must be either 'cloudflare' or 'development'.",
        )
    return mode


def _access_settings() -> tuple[str, str]:
    team_domain = os.getenv("CLOUDFLARE_ACCESS_TEAM_DOMAIN", "").rstrip("/")
    audience = os.getenv("CLOUDFLARE_ACCESS_AUD", "")
    if not team_domain or not audience:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Cloudflare Access authentication is not configured on the backend.",
        )
    if not team_domain.startswith("https://"):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CLOUDFLARE_ACCESS_TEAM_DOMAIN must be an https:// URL.",
        )
    return team_domain, audience


@lru_cache(maxsize=4)
def _jwks_client(team_domain: str) -> PyJWKClient:
    return PyJWKClient(f"{team_domain}/cdn-cgi/access/certs")


def _get_identity(request: Request) -> tuple[str, str]:
    if _auth_mode() == "development":
        return LOCAL_DEVELOPMENT_IDENTITY

    team_domain, audience = _access_settings()
    token = request.headers.get("cf-access-jwt-assertion")
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "A valid Cloudflare Access identity is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = _jwks_client(team_domain).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=team_domain,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except PyJWKClientConnectionError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Could not retrieve Cloudflare Access signing keys.",
        ) from error
    except (InvalidTokenError, PyJWKClientError) as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "The Cloudflare Access identity is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "The Cloudflare Access identity has no subject.",
        )
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "The Cloudflare Access identity has no email address.",
        )
    return subject, email.strip().lower()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    subject, email = _get_identity(request)
    created_user = False
    user = db.scalar(select(models.User).where(models.User.subject == subject))
    if user is None:
        user = models.User(
            subject=subject,
            email=email,
            name=(
                "Local Developer"
                if subject == LOCAL_DEVELOPMENT_IDENTITY[0]
                else None
            ),
        )
        db.add(user)
        try:
            db.commit()
            created_user = True
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(models.User).where(models.User.subject == subject))
            if user is None:
                raise
    elif user.email != email:
        user.email = email
        db.commit()

    if created_user:
        for table, columns in (
            ("profile_goals", "kilojoules, protein, carbohydrates, fat, sugar"),
            ("profile_theme", "accent_color"),
        ):
            legacy_table = f"legacy_{table}"
            legacy_exists = db.scalar(
                text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name"),
                {"name": legacy_table},
            )
            if legacy_exists:
                db.execute(
                    text(
                        f"INSERT OR IGNORE INTO {table} (user_id, {columns}) "
                        f"SELECT :user_id, {columns} FROM {legacy_table} LIMIT 1"
                    ),
                    {"user_id": user.id},
                )
                db.execute(text(f"DROP TABLE {legacy_table}"))
        db.commit()

    first_user_id = db.scalar(select(models.User.id).order_by(models.User.id).limit(1))
    if user.id == first_user_id:
        ingredients_updated = db.execute(
            update(models.Ingredient)
            .where(models.Ingredient.owner_id.is_(None))
            .values(owner_id=user.id)
        ).rowcount
        foods_updated = db.execute(
            update(models.Food)
            .where(models.Food.owner_id.is_(None))
            .values(owner_id=user.id)
        ).rowcount
        meals_updated = db.execute(
            update(models.Meal)
            .where(models.Meal.owner_id.is_(None))
            .values(owner_id=user.id)
        ).rowcount
        if ingredients_updated or foods_updated or meals_updated:
            db.commit()

    return user
