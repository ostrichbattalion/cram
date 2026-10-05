"""
cram/resources/display.py
Terminal rendering for the resources feature. Nothing here mutates the index
or touches disk.

Visual language matches cram's display.py (same ANSI palette, 62-column rules,
20-cell bars). The few helpers are re-declared here rather than imported, so
this package stays independent of the core display layer.
"""

import re
from .models import ResourceIndex, Resource, KINDS, STATUSES

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
C  = "\033[96m"
W  = "\033[97m"
DIM= "\033[2m"
RST= "\033[0m"

WIDTH      = 62
BAR_WIDTH  = 20
NAME_WIDTH = 44

STATUS_ICON = {
    "new":      f"{DIM}○{RST}",
    "started":  f"{Y}◐{RST}",
    "reviewed": f"{G}●{RST}",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _header(title: str):
    print(f"\n{W}{'─' * WIDTH}{RST}")
    print(f"{W}  {title}{RST}")
    print(f"{W}{'─' * WIDTH}{RST}")


def _bar(counts: dict[str, int]) -> str:
    """Two-tone bar: reviewed (green) then started (yellow) then remaining."""
    total = sum(counts.values()) or 1
    rev   = round(counts["reviewed"] / total * BAR_WIDTH)
    sta   = min(round(counts["started"] / total * BAR_WIDTH), BAR_WIDTH - rev)
    rest  = BAR_WIDTH - rev - sta
    return f"{G}{'█' * rev}{Y}{'▒' * sta}{DIM}{'─' * rest}{RST}"


def _pct(counts: dict[str, int]) -> int:
    total = sum(counts.values())
    return int(counts["reviewed"] / total * 100) if total else 0


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit in ("B", "KB") else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n}B"


# ── Views ─────────────────────────────────────────────────────────────────────

def print_no_index():
    print(f"\n{Y}No resources tracked yet.{RST}")
    print("  Point cram at your semester folder once:")
    print(f'  {W}python cram.py --res-scan "C:\\path\\to\\Semester 1"{RST}\n')


def print_summary(index: ResourceIndex):
    """One line per module: reviewed bar, counts, unwatched recordings."""
    _header("CRAM  ─  Course Content")
    print(f"  {'Module':<30} {'Reviewed':<22} {'Done':<7} {'To do':>5}")
    print(f"  {DIM}{'─' * 30} {'─' * 22} {'─' * 7} {'─' * 5}{RST}")

    all_counts = {s: 0 for s in STATUSES}
    for name, _code in index.modules():
        rs = index.for_module(name)
        if not rs:
            continue
        c = index.counts(rs)
        for s in STATUSES:
            all_counts[s] += c[s]
        todo = c["new"] + c["started"]
        done = f"{c['reviewed']}/{len(rs)}"
        print(f"  {_clip(name, 30):<30} [{_bar(c)}] {done:<7} {todo:>5}")

    total = sum(all_counts.values())
    print(f"  {DIM}{'─' * (WIDTH - 2)}{RST}")
    done = f"{all_counts['reviewed']}/{total}"
    print(f"  {'All modules':<30} [{_bar(all_counts)}] {done:<7} "
          f"{all_counts['new'] + all_counts['started']:>5}")

    # Call out unwatched recordings: usually the most time-sensitive thing
    unwatched = [r for r in index.items.values()
                 if r.kind == "recording" and not r.missing and r.status != "reviewed"]
    if unwatched:
        print(f"\n  {Y}▶ {len(unwatched)} workshop recording(s) not yet reviewed{RST}")
        for r in sorted(unwatched, key=lambda r: (r.module, r.name)):
            print(f"    {DIM}{_clip(r.module, 30):<30}{RST} {_clip(r.title, 28)}")

    _footer(index)


def print_module(index: ResourceIndex, module: str, todo_only: bool = False):
    """Every resource in one module, grouped by kind and numbered for --res-mark."""
    rs = index.for_module(module)
    c  = index.counts(rs)
    code = next((r.code for r in rs), "")
    _header(f"CRAM  ─  {module}  {DIM}({code}){RST}")
    print(f"  Reviewed: [{_bar(c)}] {_pct(c):>3}%  "
          f"{G}{c['reviewed']} done{RST}  {Y}{c['started']} started{RST}  "
          f"{DIM}{c['new']} new{RST}")

    current_kind = None
    shown = 0
    for i, r in enumerate(rs, start=1):
        if todo_only and r.status == "reviewed":
            continue
        if r.kind != current_kind:
            current_kind = r.kind
            print(f"\n  {C}{KINDS.get(r.kind, r.kind).upper()}{RST}")
        _print_line(i, r)
        shown += 1

    if todo_only and shown == 0:
        print(f"\n  {G}✓ Everything in this module is reviewed.{RST}")

    missing = [r for r in index.for_module(module, include_missing=True) if r.missing]
    if missing:
        print(f"\n  {DIM}{len(missing)} file(s) no longer found on disk (status kept):{RST}")
        for r in missing:
            where = r.rel_path.split("/", 1)[-1]          # path inside the module folder
            print(f"    {DIM}{_clip(where, WIDTH - 4)}{RST}")

    _footer(index, module_hint=module)


def print_todo(index: ResourceIndex):
    """Everything not yet reviewed, across all modules."""
    _header("CRAM  ─  Still to Review")
    any_left = False
    for name, _code in index.modules():
        rs = index.for_module(name)
        todo = [(i, r) for i, r in enumerate(rs, start=1) if r.status != "reviewed"]
        if not todo:
            continue
        any_left = True
        print(f"\n  {W}▶ {name.upper()}{RST}  {DIM}{len(todo)} left{RST}")
        for i, r in todo:
            _print_line(i, r, show_kind=True)
    if not any_left:
        print(f"\n  {G}✓ Everything is reviewed.{RST}")
    _footer(index)


def _print_line(number: int, r: Resource, show_kind: bool = False):
    when = f"{DIM}{r.status_date}{RST}" if r.status_date else ""
    kind = f"{DIM}{KINDS.get(r.kind, r.kind).split()[0].lower():<10}{RST} " if show_kind else ""
    name_col = DIM if r.status == "reviewed" else W
    print(f"  {DIM}{number:>3}{RST}  {STATUS_ICON[r.status]}  {kind}"
          f"{name_col}{_clip(r.title, NAME_WIDTH - (11 if show_kind else 0)):<{NAME_WIDTH - (11 if show_kind else 0)}}{RST}"
          f" {DIM}{r.extension:<4}{RST} {when}")


def _footer(index: ResourceIndex, module_hint: str | None = None):
    hint = f'"{module_hint.split()[0].lower()}"' if module_hint else '"module"'
    print(f"\n  {DIM}○ new   ◐ started   ● reviewed{RST}")
    print(f"  {DIM}Mark:  python cram.py --res-mark {hint} 3 done   (also 1-5, 2,4, all){RST}")
    print(f"  {DIM}Open:  python cram.py --res-open {hint} 3{RST}")
    if index.scanned_at:
        print(f"  {DIM}Last scanned {index.scanned_at}  ·  --res-scan to refresh{RST}")
    print(f"{DIM}{'─' * WIDTH}{RST}\n")


def format_scan_result(result, root: str) -> str:
    lines = [f"🔎  Scanned {root}"]
    if result.added:
        lines.append(f"   {G}+ {len(result.added)} new resource(s){RST}")
    if result.moved:
        lines.append(f"   {C}↪ {len(result.moved)} moved or renamed (review status kept){RST}")
    if result.missing:
        lines.append(f"   {Y}? {len(result.missing)} no longer found (kept, flagged missing){RST}")
    lines.append(f"   {DIM}{result.unchanged} unchanged{RST}")
    return "\n".join(lines)
