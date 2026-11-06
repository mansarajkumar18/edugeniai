from typing import Optional, Tuple
from pydantic import BaseModel, Field

class ErrorResponse(BaseModel):
    """Standardized error response model."""
    error: str = Field(..., description="Sanitized human-readable error description")

def clean_text_string(val: str, field_name: str, min_len: int, max_len: int) -> str:
    """
    Validates and cleans input strings:
    - Rejects non-string types
    - Rejects null bytes (\x00)
    - Strips leading/trailing whitespace
    - Enforces min_len and max_len bounds
    """
    if not isinstance(val, str):
        raise ValueError(f"Please provide a valid {field_name}.")
    cleaned = val.strip()
    if "\x00" in cleaned:
        raise ValueError(f"{field_name.capitalize()} contains invalid null characters.")
    if len(cleaned) < min_len:
        raise ValueError(f"Please provide a valid {field_name}.")
    if len(cleaned) > max_len:
        raise ValueError(f"{field_name.capitalize()} exceeds the maximum allowed length of {max_len} characters.")
    return cleaned

def validate_query_param(val: Optional[str], field_name: str, max_length: int = 5000) -> Tuple[str, str]:
    """
    Validates and sanitizes optional query parameters.
    Returns (cleaned_string, error_message).
    """
    if not val or not isinstance(val, str) or not val.strip():
        return "", f"Please provide a valid {field_name}."
    cleaned = val.strip()
    if "\x00" in cleaned:
        return "", f"{field_name.capitalize()} contains invalid null characters."
    if len(cleaned) > max_length:
        return "", f"{field_name.capitalize()} exceeds the maximum allowed length of {max_length} characters."
    return cleaned, ""

def clean_optional_text_string(val: Optional[str], field_name: str, max_len: int = 1000) -> Optional[str]:
    """
    Validates and cleans optional string fields:
    - Returns None if val is None or empty whitespace
    - Rejects null bytes (\\x00)
    - Enforces max_len bound
    """
    if val is None:
        return None
    if not isinstance(val, str):
        raise ValueError(f"Please provide a valid {field_name}.")
    cleaned = val.strip()
    if not cleaned:
        return None
    if "\x00" in cleaned:
        raise ValueError(f"{field_name.capitalize()} contains invalid null characters.")
    if len(cleaned) > max_len:
        raise ValueError(f"{field_name.capitalize()} exceeds the maximum allowed length of {max_len} characters.")
    return cleaned

