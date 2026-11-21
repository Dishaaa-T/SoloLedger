"""
Pydantic schemas for SoloLedger request and response bodies.

Pydantic v2 is used. Email and phone checks are done with regular
expressions, so no extra packages are needed.
"""

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

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


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

# Largest amount the API accepts, in INR (major units).
MAX_INVOICE_AMOUNT = Decimal("10000000")


def _check_due_not_before_issue(issue_date: date, due_date: date) -> None:
    if due_date < issue_date:
        raise ValueError("Due date cannot be earlier than issue date.")


class InvoiceCreate(BaseModel):
    """Body for POST /invoices. Every field except description is required.

    `amount` is in INR (major units), for example 25000.00. The router stores
    it as integer cents.
    """

    client_id: int = Field(gt=0)
    invoice_number: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    amount: Decimal = Field(
        gt=Decimal("0"),
        le=MAX_INVOICE_AMOUNT,
        decimal_places=2,
    )
    issue_date: date
    due_date: date

    @field_validator("invoice_number", mode="before")
    @classmethod
    def _strip_number(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def _blank_description_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _check_dates(self):
        _check_due_not_before_issue(self.issue_date, self.due_date)
        return self


class InvoiceUpdate(BaseModel):
    """Body for PUT /invoices/{id}. Every field is optional.

    Omitted fields are left unchanged. An explicit null is rejected for every
    field except description, where it clears the stored value. Status and
    paid_date are not accepted here; use POST /invoices/{id}/mark-paid.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: int | None = Field(default=None, gt=0)
    invoice_number: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    amount: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        le=MAX_INVOICE_AMOUNT,
        decimal_places=2,
    )
    issue_date: date | None = None
    due_date: date | None = None

    @field_validator(
        "client_id", "invoice_number", "amount", "issue_date", "due_date",
        mode="before",
    )
    @classmethod
    def _reject_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value

    @field_validator("invoice_number", mode="before")
    @classmethod
    def _strip_number(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def _blank_description_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _check_dates(self):
        # Only checks dates sent together in this request. The router checks
        # the merged dates against the stored invoice.
        if self.issue_date is not None and self.due_date is not None:
            _check_due_not_before_issue(self.issue_date, self.due_date)
        return self


class MarkPaidRequest(BaseModel):
    """Optional body for POST /invoices/{id}/mark-paid. Defaults to today."""

    paid_date: date | None = None


class ClientSummary(BaseModel):
    """The client details nested inside an invoice."""

    id: int
    name: str
    email: str | None
    company: str | None


class InvoiceOut(BaseModel):
    """An invoice as returned by the API.

    `amount` is INR with 2 decimal places. It is sent as a JSON number,
    for example 25000.0.
    """

    id: int
    client_id: int
    invoice_number: str
    description: str | None
    amount: Decimal
    status: Literal["pending", "paid", "overdue"]
    issue_date: date
    due_date: date
    paid_date: date | None
    created_at: str
    client: ClientSummary

    @field_serializer("amount")
    def _amount_as_number(self, value: Decimal) -> float:
        return float(value)

