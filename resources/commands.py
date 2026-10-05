"""
cram/resources/commands.py
Command handlers for the resources feature. Each one loads the index, acts,
saves, and returns a status message. No display formatting beyond the message.
"""

import os
import subprocess
import sys

from .models import ResourceIndex, parse_status, parse_numbers
from .scanner import scan
from .store import load_index, save_index
from .display import format_scan_result


def cmd_scan(root: str | None = None) -> str:
    """Scan the semester folder. The path is remembered after the first run."""
    index = load_index()
    root = root or index.root
    if not root:
        return ('❌  No folder given. Run once with the path to your semester folder:\n'
                '    python cram.py --res-scan "C:\\path\\to\\Semester 1"')
    root = os.path.abspath(os.path.expanduser(root))
    try:
        found = scan(root)
    except FileNotFoundError:
        return f"❌  Folder not found: {root}"
    if not found and not index.items:
        return (f"❌  No module folders found in {root}\n"
                f"    Module folders need a code in brackets, e.g. "
                f"'Software Engineering 700 (2026M1SEM700M)'.")
    result = index.reconcile(found, root)
    save_index(index)
    return format_scan_result(result, root)


def _resolve(index: ResourceIndex, module_query: str):
    module = index.find_module(module_query)
    if not module:
        names = ", ".join(n for n, _ in index.modules()) or "none scanned yet"
        return None, f"❌  Module not found: '{module_query}'  (known: {names})"
    return module, None


def cmd_mark(module_query: str, items: str, status_text: str) -> str:
    """
    --res-mark "software" 3 done            one item by number
    --res-mark "hci" 1-9 started            a range (also 2,4 and all)
    --res-mark "ai" "study guide" done      every item whose file name contains the text
    --res-mark all "Workshop 1 - 2026-08" done    name match across every module
    """
    index = load_index()
    status = parse_status(status_text)
    if not status:
        return f"❌  Unknown status '{status_text}'. Use new | started | done."

    every_module = module_query.lower().strip() == "all"
    if every_module:
        modules = [name for name, _ in index.modules()]
    else:
        module, err = _resolve(index, module_query)
        if err:
            return err
        modules = [module]

    looks_numeric = all(ch.isdigit() or ch in ",- " for ch in items) or items.lower().strip() == "all"
    if every_module and looks_numeric:
        return ("❌  With 'all' modules, give part of a file name instead of numbers,\n"
                '    e.g. --res-mark all "Workshop 1 - 2026-08" done')

    picked = []
    for module in modules:
        rs = index.for_module(module)
        if looks_numeric:
            picks = parse_numbers(items, len(rs))
            if not picks:
                return f"❌  '{items}' isn't a valid item number for {module} (1–{len(rs)})."
            picked += [rs[n - 1] for n in picks]
        else:
            needle = items.lower().strip()
            picked += [r for r in rs if needle in r.name.lower()]

    if not picked:
        return f"❌  No items with '{items}' in the file name."
    for r in picked:
        r.set_status(status)
    save_index(index)

    icon = {"new": "○", "started": "◐", "reviewed": "●"}[status]
    if len(picked) == 1:
        return f"{icon}  {picked[0].module}: '{picked[0].title}' → {status}"
    lines = [f"{icon}  {len(picked)} items → {status}"]
    lines += [f"     {r.module}: {r.title}" for r in picked]
    return "\n".join(lines)


def cmd_open(module_query: str, number: str) -> str:
    """Open a resource in its default app and mark it started if it was new."""
    index = load_index()
    module, err = _resolve(index, module_query)
    if err:
        return err
    rs = index.for_module(module)
    picks = parse_numbers(number, len(rs))
    if not picks or len(picks) != 1:
        return f"❌  Give one item number for {module} (1–{len(rs)})."
    r = rs[picks[0] - 1]
    full = os.path.join(index.root or "", *r.rel_path.split("/"))
    if not os.path.exists(full):
        return f"❌  File not found: {full}\n    Run --res-scan if you've moved things."
    try:
        _open_file(full)
    except OSError as e:
        return f"❌  Couldn't open {r.name}: {e}"
    if r.status == "new":
        r.set_status("started")
        save_index(index)
        return f"◐  Opened '{r.title}' and marked it started."
    return f"↗  Opened '{r.title}'."


def _open_file(path: str):
    if sys.platform.startswith("win"):
        os.startfile(path)                                   # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
