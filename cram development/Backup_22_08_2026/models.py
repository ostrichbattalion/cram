"""
cram/models.py
Core data model: Module → Topic → Session / ConfidenceEvent
All display and persistence logic lives elsewhere.
"""

from datetime import datetime, date

# ── Constants ────────────────────────────────────────────────────────────────

CONTACT_HOURS_PER_MODULE = 3        # fixed for all distance learning modules
HOURS_PER_CREDIT         = 10       # SAQA definition
ASSIGNMENT_HOURS_PER_Q   = 2        # SAQA-aligned estimate per assignment question

# Notional hour distribution across the five study phases (must sum to 1.0)
PHASE_WEIGHTS = {
    1: 0.20,   # First Exposure       — CA topics, first pass
    2: 0.25,   # Active Learning      — CA topics, deepen + assignment
    3: 0.15,   # CA Review            — consolidate before CA test
    4: 0.20,   # New Content          — Final topics, first pass
    5: 0.20,   # Final Review         — all topics, second pass
}

# Neglect thresholds (days since last session on a topic)
NEGLECT_WARN_DAYS  = 4
NEGLECT_ALERT_DAYS = 7

# Confidence level labels
CONFIDENCE_LABELS = {
    1: "First exposure done — shaky",
    2: "Working understanding — can follow examples",
    3: "Solid — could explain it",
    4: "Mastered — exam confident",
}


# ── ConfidenceEvent ──────────────────────────────────────────────────────────

class ConfidenceEvent:
    """
    Records a single confidence level change on a topic.
    Tracks the date and cumulative hours studied at the moment of change.
    """
    def __init__(self, level: int, date_str: str, hours_at_change: float):
        self.level          = level
        self.date_str       = date_str
        self.hours_at_change = float(hours_at_change)

    @property
    def date(self) -> datetime:
        return datetime.strptime(self.date_str, "%Y-%m-%d")

    def to_dict(self) -> dict:
        return {
            "level":           self.level,
            "date":            self.date_str,
            "hours_at_change": self.hours_at_change,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceEvent":
        return cls(d["level"], d["date"], d["hours_at_change"])


# ── Session ──────────────────────────────────────────────────────────────────

class Session:
    """A single study session logged against a specific topic."""
    def __init__(self, date_str: str, hours: float, note: str = ""):
        self.date_str = date_str
        self.hours    = float(hours)
        self.note     = note

    @property
    def date(self) -> datetime:
        return datetime.strptime(self.date_str, "%Y-%m-%d")

    def to_dict(self) -> dict:
        return {"date": self.date_str, "hours": self.hours, "note": self.note}

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(d["date"], d["hours"], d.get("note", ""))


# ── Topic ────────────────────────────────────────────────────────────────────

class Topic:
    """
    A single learner-guide topic belonging to a module.
    phase: 1-3 = CA arc,  4-5 = Final arc
           (phases map to study phases, not topic numbers)
    arc:   'ca' | 'final'
    """
    def __init__(self, number: int, name: str, arc: str,
                 sessions: list = None,
                 confidence_history: list = None):
        self.number   = number
        self.name     = name
        self.arc      = arc          # 'ca' or 'final'
        self.sessions: list[Session] = sessions or []
        self.confidence_history: list[ConfidenceEvent] = confidence_history or []

        # Seed confidence history at level 1 if this is a fresh topic
        if not self.confidence_history:
            self.confidence_history.append(
                ConfidenceEvent(1, datetime.now().strftime("%Y-%m-%d"), 0.0)
            )

    # ── Derived properties ───────────────────────────────────────────────────

    @property
    def confidence(self) -> int:
        return self.confidence_history[-1].level

    @property
    def hours_studied(self) -> float:
        return round(sum(s.hours for s in self.sessions), 2)

    @property
    def last_session_date(self) -> datetime | None:
        if not self.sessions:
            return None
        return max(s.date for s in self.sessions)

    def days_since_last_session(self) -> int | None:
        if not self.last_session_date:
            return None
        return (datetime.now() - self.last_session_date).days

    def neglect_level(self) -> str | None:
        days = self.days_since_last_session()
        if days is None:
            return None
        if days >= NEGLECT_ALERT_DAYS:
            return "alert"
        if days >= NEGLECT_WARN_DAYS:
            return "warn"
        return None

    def hours_at_current_confidence(self) -> float:
        """Hours logged since the last confidence level change."""
        last_event = self.confidence_history[-1]
        return round(self.hours_studied - last_event.hours_at_change, 2)

    # ── Mutations ────────────────────────────────────────────────────────────

    def log_session(self, hours: float, note: str = ""):
        today = datetime.now().strftime("%Y-%m-%d")
        self.sessions.append(Session(today, hours, note))

    def set_confidence(self, level: int):
        if level not in CONFIDENCE_LABELS:
            raise ValueError(f"Confidence must be 1-4, got {level}")
        if level == self.confidence:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        self.confidence_history.append(
            ConfidenceEvent(level, today, self.hours_studied)
        )

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "number":             self.number,
            "name":               self.name,
            "arc":                self.arc,
            "sessions":           [s.to_dict() for s in self.sessions],
            "confidence_history": [e.to_dict() for e in self.confidence_history],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Topic":
        sessions = [Session.from_dict(s) for s in d.get("sessions", [])]
        confidence_history = [
            ConfidenceEvent.from_dict(e)
            for e in d.get("confidence_history", [])
        ]
        t = cls(d["number"], d["name"], d["arc"],
                sessions=sessions,
                confidence_history=confidence_history)
        return t


# ── Assignment ───────────────────────────────────────────────────────────────

class Assignment:
    """Tracks question-based assignment progress for a module."""
    def __init__(self, total_q: int, completed_q: int = 0,
                 due_date_str: str = None, hours_spent: float = 0.0):
        self.total_q     = total_q
        self.completed_q = int(completed_q)
        self.due_date_str = due_date_str     # None until released
        self.hours_spent  = float(hours_spent)

    @property
    def due_date(self) -> datetime | None:
        if not self.due_date_str:
            return None
        return datetime.strptime(self.due_date_str, "%Y-%m-%d")

    @property
    def notional_hours(self) -> float:
        """SAQA-aligned estimate: 2 hrs per question."""
        return self.total_q * ASSIGNMENT_HOURS_PER_Q

    @property
    def percent_complete(self) -> int:
        if self.total_q == 0:
            return 100
        return min(int((self.completed_q / self.total_q) * 100), 100)

    @property
    def is_complete(self) -> bool:
        return self.completed_q >= self.total_q

    def days_until_due(self) -> int | None:
        if not self.due_date:
            return None
        return (self.due_date - datetime.now()).days

    def complete_questions(self, count: int):
        self.completed_q = min(self.completed_q + int(count), self.total_q)

    def to_dict(self) -> dict:
        return {
            "total_q":      self.total_q,
            "completed_q":  self.completed_q,
            "due_date":     self.due_date_str,
            "hours_spent":  self.hours_spent,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Assignment":
        return cls(
            d["total_q"],
            d.get("completed_q", 0),
            d.get("due_date"),
            d.get("hours_spent", 0.0),
        )


# ── Assessment ───────────────────────────────────────────────────────────────

class Assessment:
    """CA test or Final exam for a module."""
    def __init__(self, kind: str, due_date_str: str = None):
        if kind not in ("ca", "final"):
            raise ValueError("kind must be 'ca' or 'final'")
        self.kind         = kind          # 'ca' or 'final'
        self.due_date_str = due_date_str  # None until released by institution

    @property
    def due_date(self) -> datetime | None:
        if not self.due_date_str:
            return None
        return datetime.strptime(self.due_date_str, "%Y-%m-%d")

    def days_until_due(self) -> int | None:
        if not self.due_date:
            return None
        return (self.due_date - datetime.now()).days

    def to_dict(self) -> dict:
        return {"kind": self.kind, "due_date": self.due_date_str}

    @classmethod
    def from_dict(cls, d: dict) -> "Assessment":
        return cls(d["kind"], d.get("due_date"))


# ── Module ───────────────────────────────────────────────────────────────────

class Module:
    """
    Top-level container for a single university module.
    All notional hour calculations are derived — nothing is manually set
    except credits, topic names, and assignment question count.
    """
    def __init__(self, code: str, name: str, nqf_level: int, credits: int,
                 topics: list = None,
                 assignment: Assignment = None,
                 ca: Assessment = None,
                 final: Assessment = None,
                 current_phase: int = 1,
                 ca_written: bool = False,
                 archived: bool = False):
        self.code          = code
        self.name          = name
        self.nqf_level     = nqf_level
        self.credits       = credits
        self.topics: list[Topic]    = topics or []
        self.assignment: Assignment = assignment
        self.ca: Assessment         = ca or Assessment("ca")
        self.final: Assessment      = final or Assessment("final")
        self.current_phase = current_phase
        self.ca_written    = ca_written
        self.archived      = archived

    @property
    def phase_label(self) -> str:
        return {
            1: "First Exposure",
            2: "Active Learning",
            3: "CA Review",
            4: "New Content",
            5: "Final Review",
        }.get(self.current_phase, "Unknown")

    # ── Notional hour budget (all derived) ───────────────────────────────────

    @property
    def notional_hours(self) -> float:
        return self.credits * HOURS_PER_CREDIT

    @property
    def contact_hours(self) -> float:
        return float(CONTACT_HOURS_PER_MODULE)

    @property
    def assignment_notional_hours(self) -> float:
        if not self.assignment:
            return 0.0
        return self.assignment.notional_hours

    @property
    def self_study_budget(self) -> float:
        """Total self-study hours after contact and assignment time."""
        return round(
            self.notional_hours
            - self.contact_hours
            - self.assignment_notional_hours,
            1
        )

    def phase_budget(self, phase: int) -> float:
        """Hours allocated to a given study phase."""
        return round(self.self_study_budget * PHASE_WEIGHTS[phase], 1)

    # ── Topic helpers ────────────────────────────────────────────────────────

    @property
    def ca_topics(self) -> list[Topic]:
        return [t for t in self.topics if t.arc == "ca"]

    @property
    def final_topics(self) -> list[Topic]:
        return [t for t in self.topics if t.arc == "final"]

    @property
    def hours_studied(self) -> float:
        return round(sum(t.hours_studied for t in self.topics), 2)

    @property
    def remaining_self_study_hours(self) -> float:
        """
        Confidence-gated early exit (Strategic_Calibration.docx, Strategy A).

        Instead of treating the flat self_study_budget as an absolute target,
        split it evenly across topics and let any topic that has already
        reached Mastered (confidence 4) drop out of the burn-down — its
        remaining share is returned to the pool. This lets the recommender
        shrink demand dynamically as real understanding is demonstrated,
        rather than continuing to schedule hours against material you've
        already nailed.
        """
        if not self.topics:
            return max(self.self_study_budget - self.hours_studied, 0.0)
        share = self.self_study_budget / len(self.topics)
        remaining = 0.0
        for t in self.topics:
            if t.confidence >= 4:
                continue  # mastered — hours cleared, returned to pool
            remaining += max(share - t.hours_studied, 0.0)
        return round(remaining, 2)

    def last_session_date(self) -> datetime | None:
        dates = [t.last_session_date for t in self.topics if t.last_session_date]
        return max(dates) if dates else None

    def days_since_last_session(self) -> int | None:
        last = self.last_session_date()
        if not last:
            return 999 # hotfix recommendaiton by Gemini
        return (datetime.now() - last).days

    def neglect_level(self) -> str | None:
        days = self.days_since_last_session()
        if days is None:
            return None
        if days >= NEGLECT_ALERT_DAYS:
            return "alert"
        if days >= NEGLECT_WARN_DAYS:
            return "warn"
        return None

    def average_confidence(self, arc: str = None) -> float:
        """Mean confidence across all topics, optionally filtered by arc."""
        topics = self.topics
        if arc:
            topics = [t for t in topics if t.arc == arc]
        if not topics:
            return 0.0
        return round(sum(t.confidence for t in topics) / len(topics), 1)

    def get_topic(self, number: int) -> Topic | None:
        for t in self.topics:
            if t.number == number:
                return t
        return None

    # ── Recommended daily hours (burn-down) ──────────────────────────────────

    def recommended_daily_hours(self, reference_date: str = None) -> float | None:
        """
        Hours per day needed across remaining self-study budget.
        Uses CA date if available and not yet passed, else final date.
        Returns None if no date is set.
        """
        today = datetime.now()

        # Pick the most relevant upcoming assessment date
        target_date = None
        if self.ca.due_date and self.ca.due_date > today:
            target_date = self.ca.due_date
        elif self.final.due_date and self.final.due_date > today:
            target_date = self.final.due_date

        if not target_date:
            return None

        days_left  = (target_date - today).days
        remaining  = self.remaining_self_study_hours
        if remaining <= 0 or days_left <= 0:
            return 0.0
        return round(remaining / days_left, 1)

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "code":       self.code,
            "name":       self.name,
            "nqf_level":  self.nqf_level,
            "credits":       self.credits,
            "current_phase": self.current_phase,
            "ca_written":    self.ca_written,
            "topics":        [t.to_dict() for t in self.topics],
            "assignment":    self.assignment.to_dict() if self.assignment else None,
            "ca":            self.ca.to_dict(),
            "final":         self.final.to_dict(),
            "archived":      self.archived,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Module":
        topics = [Topic.from_dict(t) for t in d.get("topics", [])]
        assignment = (Assignment.from_dict(d["assignment"])
                      if d.get("assignment") else None)
        ca    = Assessment.from_dict(d["ca"])    if d.get("ca")    else Assessment("ca")
        final = Assessment.from_dict(d["final"]) if d.get("final") else Assessment("final")
        return cls(
            d["code"], d["name"], d["nqf_level"], d["credits"],
            topics=topics, assignment=assignment,
            ca=ca, final=final,
            current_phase=d.get("current_phase", 1),
            ca_written=d.get("ca_written", False),
            archived=d.get("archived", False),
        )
