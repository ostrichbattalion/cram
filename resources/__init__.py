"""
cram/resources — course-content tracking feature.

A self-contained package that discovers study resources (workshop recordings,
slides, notes, past papers, prescribed reading) by scanning a semester folder,
and tracks which ones you have reviewed.

It mirrors cram's own layering in miniature and has no dependency on the core
modules (models.py, database.py, scheduler.py, display.py, commands.py):

    resources/
    ├── models.py    Resource + ResourceIndex. Pure data and logic, no I/O.
    ├── scanner.py   Reads the folder tree. Returns plain records, no state.
    ├── store.py     JSON persistence for data/resources.json.
    ├── display.py   Terminal rendering. No mutations.
    ├── commands.py  Command handlers. Calls scanner + store.
    └── cli.py       The only surface cram.py touches: register_args / handle.

Remove the package and the three lines that reference it in cram.py, and cram
runs exactly as before.
"""

from .cli import register_args, handle

__all__ = ["register_args", "handle"]
