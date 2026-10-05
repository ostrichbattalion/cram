"""
cram/resources/models.py
Resource data model. No file-system access, no persistence, no display.

ResourceIndex holds every resource ever discovered, keyed by its path relative
to the semester root. Reconciling a fresh scan against the index is pure logic
and lives here so it can be tested without touching disk.
"""

from datetime import datetime

# ── Constants ────────────────────────────────────────────────────────────────

# Review status, in the order a resource moves through them
STATUSES = ("new", "started", "reviewed")

STATUS_ALIASES = {
    "0": "new", "new": "new", "todo": "new", "reset": "new",
    "1": "started", "started": "started", "start": "started", "doing": "started",
    "2": "reviewed", "reviewed": "reviewed", "done": "reviewed", "review": "reviewed",
}

# Resource kinds, in display order, with their section labels
KINDS = {
    "recording":  "Workshop recordings",
    "class":      "Class resources",
    "notes":      "Notes",
    "past_paper": "Past papers",
    "reading":    "Prescribed reading",
    "extra":      "Additional reading",
    "other":      "Other",
}
KIND_ORDER = list(KINDS)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── Resource ─────────────────────────────────────────────────────────────────

class Resource:
    """One file inside a module folder that is worth reviewing."""

    def __init__(self, rel_path: str, module: str, code: str, kind: str,
                 name: str, size: int, status: str = "new",
                 status_date: str | None = None,
                 first_seen: str | None = None, missing: bool = False):
        self.rel_path    = rel_path     # key: path relative to semester root
        self.module      = module       # e.g. "Software Engineering 700"
        self.code        = code         # e.g. "2026M1SEM700M"
        self.kind        = kind         # one of KINDS
        self.name        = name         # file name (with extension)
        self.size        = int(size)
        self.status      = status
        self.status_date = status_date
        self.first_seen  = first_seen or _today()
        self.missing     = missing      # True if the last scan didn't find it

    # ── Derived ──────────────────────────────────────────────────────────────

    @property
    def title(self) -> str:
        """File name without its extension."""
        stem, dot, _ = self.name.rpartition(".")
        return stem if dot else self.name

    @property
    def extension(self) -> str:
        _, dot, ext = self.name.rpartition(".")
        return ext.lower() if dot else ""

    @property
    def fingerprint(self) -> tuple[str, int]:
        """Name + size: how a moved or re-sorted file is recognised."""
        return (self.name.lower(), self.size)

    @property
    def sort_key(self) -> tuple:
        kind_rank = KIND_ORDER.index(self.kind) if self.kind in KIND_ORDER else 99
        return (kind_rank, self.rel_path.lower())

    # ── Mutations ────────────────────────────────────────────────────────────

    def set_status(self, status: str):
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}")
        self.status      = status
        self.status_date = _today() if status != "new" else None

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "module":      self.module,
            "code":        self.code,
            "kind":        self.kind,
            "name":        self.name,
            "size":        self.size,
            "status":      self.status,
            "status_date": self.status_date,
            "first_seen":  self.first_seen,
            "missing":     self.missing,
        }

    @classmethod
    def from_dict(cls, rel_path: str, d: dict) -> "Resource":
        return cls(rel_path, d["module"], d.get("code", ""), d["kind"],
                   d["name"], d.get("size", 0), d.get("status", "new"),
                   d.get("status_date"), d.get("first_seen"),
                   d.get("missing", False))


# ── ResourceIndex ────────────────────────────────────────────────────────────

class ScanResult:
    """What changed when a scan was reconciled into the index."""
    def __init__(self):
        self.added:   list[Resource] = []
        self.moved:   list[tuple[str, Resource]] = []   # (old path, resource)
        self.missing: list[Resource] = []
        self.unchanged = 0


class ResourceIndex:
    """All known resources plus the semester root they were scanned from."""

    def __init__(self, root: str | None = None,
                 items: dict[str, Resource] | None = None,
                 scanned_at: str | None = None):
        self.root       = root
        self.items      = items or {}
        self.scanned_at = scanned_at

    # ── Queries ──────────────────────────────────────────────────────────────

    def modules(self) -> list[tuple[str, str]]:
        """(module name, code) pairs, sorted by name."""
        seen = {(r.module, r.code) for r in self.items.values()}
        return sorted(seen)

    def for_module(self, module: str, include_missing: bool = False) -> list[Resource]:
        """A module's resources in stable display order. Numbers shown to the
        user are 1-based positions in this list."""
        rs = [r for r in self.items.values()
              if r.module == module and (include_missing or not r.missing)]
        return sorted(rs, key=lambda r: r.sort_key)

    def find_module(self, query: str) -> str | None:
        """
        Match a module, case-insensitive, in this order:
        exact name or code  ->  initials ("ai", "hci", "se")  ->  partial name or code.
        Initials come before partial matches so "se" means Software Engineering,
        not the "se" inside "Cyber Security".
        """
        q = query.lower().strip()
        mods = self.modules()
        for name, code in mods:
            if name.lower() == q or code.lower() == q:
                return name
        for name, code in mods:
            initials = "".join(w[0] for w in name.lower().split() if w[0].isalpha())
            if q == initials:
                return name
        for name, code in mods:
            if q in name.lower() or (code and q in code.lower()):
                return name
        return None

    @staticmethod
    def counts(resources: list[Resource]) -> dict[str, int]:
        c = {s: 0 for s in STATUSES}
        for r in resources:
            c[r.status] += 1
        return c

    # ── Reconcile a scan ─────────────────────────────────────────────────────

    def reconcile(self, found: list[dict], root: str) -> ScanResult:
        """
        Merge freshly scanned records into the index.

        found: list of {rel_path, module, code, kind, name, size}
        - Known paths are refreshed (module/kind may change if folders were renamed).
        - A new path whose name+size matches a resource that has disappeared is
          treated as the same file moved, so its review status carries over.
        - Anything previously known but not found is flagged missing, never deleted.
        """
        result   = ScanResult()
        self.root = root
        by_path  = {f["rel_path"]: f for f in found}

        # Resources that vanished from their old path, available to be "moved"
        vanished = {r.fingerprint: r for p, r in self.items.items() if p not in by_path}

        new_items: dict[str, Resource] = {}
        for path, f in by_path.items():
            if path in self.items:
                r = self.items[path]
                r.module, r.code, r.kind, r.size = f["module"], f["code"], f["kind"], f["size"]
                r.name, r.missing = f["name"], False
                result.unchanged += 1
            else:
                fp = (f["name"].lower(), int(f["size"]))
                old = vanished.pop(fp, None)
                if old:
                    old_path = old.rel_path
                    r = Resource(path, f["module"], f["code"], f["kind"], f["name"],
                                 f["size"], old.status, old.status_date, old.first_seen)
                    result.moved.append((old_path, r))
                else:
                    r = Resource(path, f["module"], f["code"], f["kind"], f["name"], f["size"])
                    result.added.append(r)
            new_items[path] = r

        # Whatever is still vanished really is gone: keep it, flagged
        for r in vanished.values():
            if not r.missing:
                result.missing.append(r)
            r.missing = True
            new_items[r.rel_path] = r

        self.items      = new_items
        self.scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        return result

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "root":       self.root,
            "scanned_at": self.scanned_at,
            "items":      {p: r.to_dict() for p, r in sorted(self.items.items())},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResourceIndex":
        items = {p: Resource.from_dict(p, v) for p, v in d.get("items", {}).items()}
        return cls(d.get("root"), items, d.get("scanned_at"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_status(text: str) -> str | None:
    return STATUS_ALIASES.get(text.lower().strip())


def parse_numbers(text: str, upper: int) -> list[int] | None:
    """
    Parse "3", "1,4,7", "2-5" or "all" into sorted 1-based numbers.
    Returns None if anything is malformed or out of range.
    """
    text = text.strip().lower()
    if text == "all":
        return list(range(1, upper + 1))
    nums: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            if not (a.strip().isdigit() and b.strip().isdigit()):
                return None
            lo, hi = int(a), int(b)
            if lo > hi:
                lo, hi = hi, lo
            nums.update(range(lo, hi + 1))
        elif part.isdigit():
            nums.add(int(part))
        else:
            return None
    if not nums or min(nums) < 1 or max(nums) > upper:
        return None
    return sorted(nums)
