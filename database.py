"""
cram/database.py
JSON persistence layer. Nothing here knows about display or CLI logic.

File structure:
  data/modules.json
    {
      "active":   [ ...Module dicts... ],
      "archived": [ ...Module dicts... ]
    }
"""

import json
import os
from models import Module

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "modules.json")


def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def _load_raw() -> tuple[list[Module], list[Module]]:
    """Return (active, archived) module lists from disk."""
    if not os.path.exists(DATA_FILE):
        return [], []
    with open(DATA_FILE, "r") as f:
        raw = json.load(f)
    active   = [Module.from_dict(d) for d in raw.get("active",   [])]
    archived = [Module.from_dict(d) for d in raw.get("archived", [])]
    return active, archived


def _save_raw(active: list[Module], archived: list[Module]):
    _ensure_data_dir()
    with open(DATA_FILE, "w") as f:
        json.dump(
            {
                "active":   [m.to_dict() for m in active],
                "archived": [m.to_dict() for m in archived],
            },
            f, indent=4
        )


# ── Public API ───────────────────────────────────────────────────────────────

def load_active() -> list[Module]:
    active, _ = _load_raw()
    return active


def load_archived() -> list[Module]:
    _, archived = _load_raw()
    return archived


def save_active(modules: list[Module]):
    """Save active modules, leaving archived list untouched."""
    _, archived = _load_raw()
    _save_raw(modules, archived)


def find_module(modules: list[Module], query: str) -> Module | None:
    """
    Find a module by name. Exact match preferred, partial match fallback.
    Case-insensitive.
    """
    query = query.lower().strip()
    for m in modules:
        if m.name.lower() == query:
            return m
    for m in modules:
        if query in m.name.lower():
            return m
    return None


def find_topic(module: Module, topic_ref: str) -> object | None:
    """
    Find a topic within a module by number or partial name match.
    topic_ref can be a number string ("3") or a name fragment ("neural").
    """
    # Try numeric first
    if topic_ref.isdigit():
        return module.get_topic(int(topic_ref))
    # Partial name match
    query = topic_ref.lower()
    for t in module.topics:
        if query in t.name.lower():
            return t
    return None


def archive_module(query: str) -> Module | None:
    """Move a named active module to archived. Returns the module or None."""
    active, archived = _load_raw()
    target = find_module(active, query)
    if target:
        active.remove(target)
        target.archived = True
        archived.append(target)
        _save_raw(active, archived)
    return target


def set_date(query: str, kind: str, date_str: str) -> Module | None:
    """
    Set ca or final date on a module. kind = 'ca' | 'final'.
    Returns updated module or None if not found.
    """
    active, _ = _load_raw()
    target = find_module(active, query)
    if target:
        if kind == "ca":
            target.ca.due_date_str = date_str
        elif kind == "final":
            target.final.due_date_str = date_str
        save_active(active)
    return target


def advance_phase(query: str) -> Module | None:
    """Advance a module to the next study phase (max 5)."""
    active, _ = _load_raw()
    target = find_module(active, query)
    if target and target.current_phase < 5:
        target.current_phase += 1
        if target.current_phase == 4:
            target.ca_written = True
        save_active(active)
    return target


def mark_ca_written(query: str) -> Module | None:
    """Mark the CA test as written and advance to phase 4."""
    active, _ = _load_raw()
    target = find_module(active, query)
    if target:
        target.ca_written = True
        if target.current_phase < 4:
            target.current_phase = 4
        save_active(active)
    return target
