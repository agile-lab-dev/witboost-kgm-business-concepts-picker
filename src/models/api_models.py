"""
Pydantic models that match the Custom URL Picker OpenAPI contract.
"""

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class Item(BaseModel):
    """A single drop-down option shown in the Witboost UI."""

    model_config = ConfigDict(extra="allow")  # OpenAPI spec uses additionalProperties: true

    id: str
    value: str | None = None
    description: str | None = None
    referenceGlossary: str | None = None


# ---------------------------------------------------------------------------
# Validation models
# ---------------------------------------------------------------------------

class SelectedObject(BaseModel):
    """An item previously selected by the user, sent back for validation."""

    id: str


class ValidationRequest(BaseModel):
    """Body of POST /v1/resources/validate."""

    selectedObjects: list[SelectedObject]
    queryParameters: dict | None = None


class ValidationErrorDetail(BaseModel):
    error: str
    suggestion: str | None = None


class ValidationErrorResponse(BaseModel):
    errors: list[ValidationErrorDetail]


# ---------------------------------------------------------------------------
# Error models
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    errors: list[str]
