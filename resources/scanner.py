"""
cram/resources/scanner.py
Walks a semester folder and returns plain records describing each resource.
Reads the file system only; holds no state and writes nothing.

Expected layout (the one Richfield modules use):

    <semester root>/
    └── Software Engineering 700 (2026M1SEM700M)/
        ├── Lectures/               -> recording
        ├── Class Resources/        -> class
        ├── Notes/                  -> notes
        ├── Past Papers/            -> past_paper
        ├── Prescribed Resources/   -> reading
        │   └── Additional Reading/ -> extra
        └── Assignments/            (your own work: skipped)

Files directly inside a module folder (e.g. the Table of Contents .txt) are
skipped. Folders that don't look like a module (no "(CODE)" suffix, or names
starting with "_" or ".") are skipped too.
"""

import os
import re

# Sub-folder name (lower-case) -> resource kind. None means skip the folder.
FOLDER_KINDS = {
    "lectures":             "recording",
    "recordings":           "recording",
    "workshops":            "recording",
    "class resources":      "class",
    "slides":               "class",
    "notes":                "notes",
    "past papers":          "past_paper",
    "prescribed resources": "reading",
    "additional reading":   "extra",
    "assignments":          None,
}

# File types worth reviewing. Anything else (shortcuts, scripts, caches) is ignored.
INCLUDE_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".doc", ".pptx", ".ppt", ".xlsx",
    ".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3",
    ".png", ".jpg", ".jpeg", ".zip", ".md", ".txt", ".ipynb",
}

AUDIO_ONLY = {".m4a", ".mp3"}
VIDEO      = {".mp4", ".mkv", ".webm", ".mov"}

MODULE_DIR_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")

# yt-dlp style format suffix, e.g. "Lecture title.f137.mp4" / "Lecture title.f140.m4a"
_FORMAT_SUFFIX_RE = re.compile(r"\.f\d+$")


def parse_module_dir(dirname: str) -> tuple[str, str] | None:
    """'Software Engineering 700 (2026M1SEM700M)' -> ('Software Engineering 700', '2026M1SEM700M')."""
    if dirname.startswith(("_", ".")):
        return None
    m = MODULE_DIR_RE.match(dirname)
    if not m:
        return None
    return m.group("name").strip(), m.group("code")


def _kind_for(parts: list[str]) -> str | None:
    """
    Decide a file's kind from its folder path inside the module folder.
    The deepest recognised folder wins, so Prescribed Resources/Additional
    Reading is 'extra' while Prescribed Resources itself is 'reading'.
    Returns None for skipped folders (Assignments).
    """
    kind = "other"
    for i, part in enumerate(parts):
        key = part.lower().strip()
        if key in FOLDER_KINDS:
            mapped = FOLDER_KINDS[key]
            if mapped is None:
                return None
            if i == 0 or mapped == "extra":
                kind = mapped
    return kind


def _media_stem(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    return _FORMAT_SUFFIX_RE.sub("", stem).lower()


def scan(root: str) -> list[dict]:
    """
    Return one record per resource found under root:
        {rel_path, module, code, kind, name, size}
    rel_path uses forward slashes so the index is portable across machines.
    Raises FileNotFoundError if root doesn't exist.
    """
    if not os.path.isdir(root):
        raise FileNotFoundError(root)

    records: list[dict] = []
    for entry in sorted(os.listdir(root)):
        mod_path = os.path.join(root, entry)
        if not os.path.isdir(mod_path):
            continue
        parsed = parse_module_dir(entry)
        if not parsed:
            continue
        module, code = parsed

        for dirpath, dirnames, filenames in os.walk(mod_path):
            dirnames[:] = sorted(d for d in dirnames
                                 if not d.startswith((".", "_")) and d != "__pycache__")
            rel_dir = os.path.relpath(dirpath, mod_path)
            if rel_dir == ".":
                continue                     # files at module level: skip
            parts = rel_dir.replace("\\", "/").split("/")
            kind = _kind_for(parts)
            if kind is None:
                dirnames[:] = []             # don't descend into skipped folders
                continue

            # Audio tracks that duplicate a video in the same folder are skipped
            video_stems = {_media_stem(f) for f in filenames
                           if os.path.splitext(f)[1].lower() in VIDEO}

            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in INCLUDE_EXTENSIONS or fname.startswith(("~$", ".")):
                    continue
                if ext in AUDIO_ONLY and _media_stem(fname) in video_stems:
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                rel = os.path.relpath(full, root).replace("\\", "/")
                records.append({
                    "rel_path": rel, "module": module, "code": code,
                    "kind": kind, "name": fname, "size": size,
                })
    return records
