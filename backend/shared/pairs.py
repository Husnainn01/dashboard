"""
Trading pair normalization utilities.

Canonical conventions:
- Internal (models, DB keys): "USDBRL"
- API asset (PyQuotex):      "USDBRL_otc"
- Display (human):           "USD/BRL (OTC)"

Functions accept common aliases like:
"USD/BRL(OTC)", "USD/BRL", "USDBRL OTC", "USDBRL_otc", case-insensitive.
"""
from typing import Optional
import re

def _strip_common(raw: str) -> str:
    s = raw.strip().upper()
    # remove spaces and separators
    s = s.replace(" ", "")
    s = s.replace("/", "")
    # normalize otc markers
    s = s.replace("(OTC)", "")
    # Remove the specific pattern first to avoid leaving a stray underscore
    s = s.replace("_OTC", "")
    s = s.replace("OTC", "")
    # Remove any leftover non-alphanumeric characters (e.g., stray underscores)
    s = re.sub(r"[^A-Z]", "", s)
    return s

def normalize_internal(raw: Optional[str]) -> Optional[str]:
    """Normalize to internal canonical key, e.g., "USDBRL".
    Returns input if falsy.
    """
    if not raw:
        return raw
    base = _strip_common(raw)
    return base

def to_api_asset(raw: Optional[str]) -> Optional[str]:
    """Normalize to API asset format for PyQuotex, e.g., "USDBRL_otc".
    Returns input if falsy.
    """
    if not raw:
        return raw
    base = _strip_common(raw)
    return f"{base}_otc"

def to_display(raw: Optional[str]) -> Optional[str]:
    """Normalize to human-display format, e.g., "USD/BRL (OTC)".
    Returns input if falsy.
    """
    if not raw:
        return raw
    base = _strip_common(raw)
    if len(base) == 6:
        disp = f"{base[:3]}/{base[3:]} (OTC)"
    else:
        disp = f"{base} (OTC)"
    return disp
