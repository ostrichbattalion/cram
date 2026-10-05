"""
cram/resources/store.py
JSON persistence for the resource index. Nothing here knows about display,
scanning or the CLI.

File: data/resources.json (kept separate from modules.json, so the core data
file is never touched by this feature)
    {
      "root":       "C:/.../Semester 1",
      "scanned_at": "2026-10-01 22:30",
      "items": { "<relative path>": { ...Resource... }, ... }
    }
"""

import json
import os
from .models import ResourceIndex

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR       = os.path.join(BASE_DIR, "data")
RESOURCES_FILE = os.path.join(DATA_DIR, "resources.json")


def load_index(path: str = RESOURCES_FILE) -> ResourceIndex:
    if not os.path.exists(path):
        return ResourceIndex()
    with open(path, "r", encoding="utf-8") as f:
        return ResourceIndex.from_dict(json.load(f))


def save_index(index: ResourceIndex, path: str = RESOURCES_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index.to_dict(), f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)       # atomic: a crash mid-write can't corrupt the file
