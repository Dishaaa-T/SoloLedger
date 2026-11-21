"""
Pydantic schemas for SoloLedger request and response bodies.

Pydantic v2 is used. Email and phone checks are done with regular
expressions, so no extra packages are needed.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A simple, practical email shape check (not a full RFC 5322 parser).
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Phone numbers may only contain digits, spaces, +, -, ( and ).
PHONE_CHARS_RE = re.compile(r"[0-9+\-() ]+")


class _ClientFields(BaseModel):
    """Optional client fields shared by create and update schemas."""

    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("email", "phone", "company", "notes", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        """Strip whitespace; an empty string means 'no value' (None)."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email", mode="after")
    @classmethod
    def _check_email(cls, value):
        if value is None:
            return None
        value = value.lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("email is not a valid email address")
        return value

    @field_validator("phone", mode="after")
    @classmethod
    def _check_phone(cls, value):
        if value is None:
            return None
        if not PHONE_CHARS_RE.fullmatch(value):
            raise ValueError(
                "phone may only contain digits, spaces, '+', '-', '(' and ')'"
            )
        if sum(ch.isdigit() for ch in value) < 7:
            raise ValueError("phone must contain at least 7 digits")
        return value


class ClientCreate(_ClientFields):
    """Body for POST /clients. The name is required."""

    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ClientUpdate(_ClientFields):
    """Body for PUT /clients/{id}. Every field is optional.

    Omitted fields are left unchanged. For email, phone, company and notes,
    an explicit null clears the stored value. The name cannot be null.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value):
        if value is None:
            raise ValueError("name cannot be null")
        if isinstance(value, str):
            return value.strip()
        return value


class ClientOut(BaseModel):
    """A client as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    phone: str | None
    company: str | None
    notes: str | None
    created_at: str
