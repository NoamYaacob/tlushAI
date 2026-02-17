"""Glossary loader and lookup utilities for payslip line items."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NamedTuple

from ..models.payslip import LineCategory

logger = logging.getLogger(__name__)

_GLOSSARY_PATH = Path(__file__).parent / "payslip_glossary.json"


class LineItemInfo(NamedTuple):
    """Resolved info for a payslip line item."""
    canonical_key: str
    category: LineCategory
    affects_gross: bool
    affects_taxable: bool
    explanation_he: str


class FieldInfo(NamedTuple):
    """Registry entry for a user-facing field."""
    key: str
    label_he: str
    section: str
    help_he: str


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_line_items: dict[str, dict] = {}
_synonym_map: dict[str, str] = {}  # lowercase synonym -> canonical_key
_field_registry: dict[str, FieldInfo] = {}
_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _load_glossary()
    _loaded = True


def _load_glossary() -> None:
    """Parse the JSON glossary and build lookup indices."""
    global _line_items, _synonym_map, _field_registry

    data = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))

    # Line items
    for key, entry in data.get("line_items", {}).items():
        _line_items[key] = entry
        # Build synonym index (Hebrew + English names)
        for name in entry.get("hebrew_names", []):
            _synonym_map[name.strip()] = key
        for name in entry.get("english_names", []):
            _synonym_map[name.strip().lower()] = key

    # Field registry
    for key, entry in data.get("field_registry", {}).items():
        _field_registry[key] = FieldInfo(
            key=key,
            label_he=entry["label_he"],
            section=entry["section"],
            help_he=entry["help_he"],
        )

    logger.debug(
        "Glossary loaded: %d line items, %d synonyms, %d field registry entries",
        len(_line_items),
        len(_synonym_map),
        len(_field_registry),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_line(label: str, label_he: str | None = None) -> LineItemInfo | None:
    """Look up a line item by its label (English or Hebrew).

    Returns LineItemInfo if a match is found, None otherwise.
    Tries exact match first, then substring match.
    """
    _ensure_loaded()

    # 1. Exact match on canonical key
    if label in _line_items:
        return _make_info(label)

    # 2. Exact match on synonyms
    lo = label.strip().lower()
    if lo in _synonym_map:
        return _make_info(_synonym_map[lo])

    # 3. Hebrew label exact match
    if label_he:
        he = label_he.strip()
        if he in _synonym_map:
            return _make_info(_synonym_map[he])

    # 4. Substring match on synonyms
    for synonym, key in _synonym_map.items():
        if synonym in lo or (label_he and synonym in label_he):
            return _make_info(key)

    return None


def get_field_info(field_key: str) -> FieldInfo | None:
    """Look up field registry entry by key."""
    _ensure_loaded()
    return _field_registry.get(field_key)


def get_all_field_info() -> dict[str, FieldInfo]:
    """Return the complete field registry."""
    _ensure_loaded()
    return dict(_field_registry)


def get_line_item_entry(canonical_key: str) -> dict | None:
    """Return the raw glossary entry for a canonical key."""
    _ensure_loaded()
    return _line_items.get(canonical_key)


def _make_info(canonical_key: str) -> LineItemInfo:
    entry = _line_items[canonical_key]
    return LineItemInfo(
        canonical_key=canonical_key,
        category=LineCategory(entry["category"]),
        affects_gross=entry["affects_gross"],
        affects_taxable=entry["affects_taxable"],
        explanation_he=entry["explanation_he"],
    )
