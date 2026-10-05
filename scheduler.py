"""
cram/scheduler.py
WeeklyPlanner  — manages the study hour pool across a week with dynamic day states.
DailyRecommender — selects up to 2 modules to study today based on urgency + neglect.
"""

from datetime import datetime, timedelta
from models import Module, Topic, NEGLECT_WARN_DAYS, NEGLECT_ALERT_DAYS

# ── Day state budgets (hours) ─────────────────────────────────────────────────
# Calibrated 2026-08-21 for the 6-module / 70-credit Semester 1 2026 load
# (634 notional self-study hours vs a 106-day runway). See Strategic_Calibration.docx
# for the methodology — this is "Strategy B, moderate": ~55% theoretical coverage,
# matching the real-world coverage ratio achieved last semester.
DAY_BUDGETS = {
    "off":       0.0,
    "light":     1.5,
    "active":    3.0,   # weekday default (was 2.0)
    "intensive": None,  # no cap — whatever was actually logged
}

WEEKEND_DEFAULT_HOURS = 4.0   # was 3.0
WEEKDAY_DEFAULT_HOURS = 3.0   # was 2.0
SOFT_CAP_HOURS        = 6.0   # was 4.0 — raised so intensive catch-up days
                              # (pre-CA / pre-assignment pushes) aren't clipped
                              # back down to the new weekend default
WEEKLY_CARRY_FRACTION = 0.20  # max carry-over into next week as momentum

# ── Urgency scoring weights ───────────────────────────────────────────────────
# Higher score = higher priority for today's recommendation
URGENCY_CA_IMMINENT         = 50   # CA in ≤ 3 days
URGENCY_CA_SOON             = 30   # CA in ≤ 7 days
URGENCY_FINAL_IMMINENT      = 40   # Final in ≤ 7 days
URGENCY_ASSIGNMENT_IMMINENT = 45   # Assignment due in ≤ 3 days, not yet complete
URGENCY_ASSIGNMENT_SOON     = 25   # Assignment due in ≤ 10 days, not yet complete
URGENCY_NEGLECT_ALERT       = 20   # not studied in 7+ days
URGENCY_NEGLECT_WARN        = 10   # not studied in 4+ days
URGENCY_LOW_CONFIDENCE      = 15   # avg confidence ≤ 2
URGENCY_PHASE_4_5           = 5    # in final arc phases


# ── WeeklyPlanner ─────────────────────────────────────────────────────────────

class WeeklyPlanner:
    """
    Tracks the study hour pool for the current week.

    Day states are stored as a dict keyed by ISO date string:
      { "2026-05-17": {"state": "active", "logged": 1.5} }

    States: "off" | "light" | "active" | "intensive"
    """

    def __init__(self, day_log: dict = None):
        self.day_log: dict[str, dict] = day_log or {}

    def _today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _week_dates(self) -> list[str]:
        """Return ISO date strings for Mon–Sun of the current week."""
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    def _is_weekend(self, date_str: str) -> bool:
        d = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        return d >= 5

    def _default_budget(self, date_str: str) -> float:
        return WEEKEND_DEFAULT_HOURS if self._is_weekend(date_str) else WEEKDAY_DEFAULT_HOURS

    # ── Week pool maths ───────────────────────────────────────────────────────

    def weekly_pool(self) -> float:
        """Total default study hours available this week."""
        return sum(self._default_budget(d) for d in self._week_dates())

    def hours_logged_this_week(self) -> float:
        total = 0.0
        for date_str in self._week_dates():
            entry = self.day_log.get(date_str, {})
            total += entry.get("logged", 0.0)
        return round(total, 2)

    def remaining_pool(self) -> float:
        return round(max(self.weekly_pool() - self.hours_logged_this_week(), 0.0), 2)

    def active_days_remaining(self) -> int:
        """Count of remaining days this week that are not 'off'."""
        today_str = self._today_str()
        week = self._week_dates()
        remaining = [d for d in week if d >= today_str]
        count = 0
        for d in remaining:
            state = self.day_log.get(d, {}).get("state", "active")
            if state != "off":
                count += 1
        return max(count, 1)

    def recommended_today(self) -> float:
        """Hours recommended for today, respecting soft cap and day state."""
        today_str = self._today_str()
        entry = self.day_log.get(today_str, {})
        state = entry.get("state", "active")

        if state == "off":
            return 0.0
        if state == "light":
            return DAY_BUDGETS["light"]

        # Distribute remaining pool across active days left
        rec = round(self.remaining_pool() / self.active_days_remaining(), 1)
        return min(rec, SOFT_CAP_HOURS)

    def hours_logged_today(self) -> float:
        entry = self.day_log.get(self._today_str(), {})
        return entry.get("logged", 0.0)

    def day_state(self, date_str: str = None) -> str:
        date_str = date_str or self._today_str()
        return self.day_log.get(date_str, {}).get("state", "active")

    # ── Mutations ─────────────────────────────────────────────────────────────

    def set_day_state(self, state: str, date_str: str = None):
        if state not in DAY_BUDGETS:
            raise ValueError(f"State must be one of {list(DAY_BUDGETS)}")
        date_str = date_str or self._today_str()
        if date_str not in self.day_log:
            self.day_log[date_str] = {}
        self.day_log[date_str]["state"] = state

    def log_hours(self, hours: float, date_str: str = None):
        """Record hours studied on a given day (default today)."""
        date_str = date_str or self._today_str()
        if date_str not in self.day_log:
            self.day_log[date_str] = {}
        current = self.day_log[date_str].get("logged", 0.0)
        logged  = round(current + hours, 2)
        self.day_log[date_str]["logged"] = logged

        # Auto-detect intensive day
        default = self._default_budget(date_str)
        if logged > default * 1.3:
            self.day_log[date_str]["state"] = "intensive"

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return self.day_log

    @classmethod
    def from_dict(cls, d: dict) -> "WeeklyPlanner":
        return cls(day_log=d or {})


# ── DailyRecommender ──────────────────────────────────────────────────────────

class DailyRecommender:
    """
    Scores each active module and selects:
      - 1 PRIMARY  — highest urgency
      - 1 REVISIT  — second highest, different module, lighter time allocation
    Total time suggested stays within today's budget from WeeklyPlanner.
    """

    def __init__(self, modules: list[Module], planner: WeeklyPlanner):
        self.modules = [m for m in modules if not m.archived]
        self.planner = planner

    def _urgency_score(self, module: Module) -> int:
        score = 0
        today = datetime.now()

        # CA urgency
        if module.ca.due_date and not module.ca_written:
            days = (module.ca.due_date - today).days
            if days <= 3:
                score += URGENCY_CA_IMMINENT
            elif days <= 7:
                score += URGENCY_CA_SOON

        # Final urgency
        if module.final.due_date:
            days = (module.final.due_date - today).days
            if days <= 7:
                score += URGENCY_FINAL_IMMINENT

        # Assignment urgency (previously not scored at all — a module with a
        # project due in a few days but no CA/final imminent could get buried)
        if module.assignment and not module.assignment.is_complete:
            days = module.assignment.days_until_due()
            if days is not None:
                if days <= 3:
                    score += URGENCY_ASSIGNMENT_IMMINENT
                elif days <= 10:
                    score += URGENCY_ASSIGNMENT_SOON

        # Neglect
        neglect = module.neglect_level()
        if neglect == "alert":
            score += URGENCY_NEGLECT_ALERT
        elif neglect == "warn":
            score += URGENCY_NEGLECT_WARN

        # Low confidence
        if module.average_confidence() <= 2:
            score += URGENCY_LOW_CONFIDENCE

        # In final arc
        if module.current_phase >= 4:
            score += URGENCY_PHASE_4_5

        return score

    def _best_topic(self, module: Module) -> Topic | None: #Hotfix Gemini recommendaiton 17/05/2026
        """
        Pick the most important topic to work on in this module.
        
        Phase 1–3:   CA arc topics only.
        Phase 4:     Final arc topics only.
        Phase 5:     Final arc topics get absolute preference until they reach 
                     confidence level 3, which then reintroduces the CA topics.
        """
        if module.current_phase == 5:
            candidates = module.topics
        elif module.current_phase == 4:
            candidates = [t for t in module.topics if t.arc == "final"]
        else:
            candidates = [t for t in module.topics if t.arc == "ca"]

        if not candidates:
            candidates = module.topics
        if not candidates:
            return None

        def topic_priority(t: Topic):
            days = t.days_since_last_session()
            days = 999 if days is None else days
            
            if module.current_phase == 5:
                # Group 0: New final-arc topics still under baseline comprehension (Lvl < 3)
                # Group 1: The unified pool where CA topics safely compete with matured final topics
                group = 0 if (t.arc == "final" and t.confidence < 3) else 1
                return (group, t.confidence, -days)
            else:
                # Standard phases handle pre-filtered candidate subsets
                return (t.confidence, -days)

        return sorted(candidates, key=topic_priority)[0]

        # Sort: lowest confidence first, then longest neglected.
        # Explicit None check: 0 (studied today) must not be treated as falsy.
        def topic_priority(t: Topic):
            days = t.days_since_last_session()
            days = 999 if days is None else days
            # In phase 5, give a mild priority boost to final arc topics that
            # are still at confidence 1 (not yet properly covered).
            arc_penalty = 1 if (module.current_phase == 5
                                and t.arc == "ca"
                                and t.confidence >= 2) else 0
            return (arc_penalty, t.confidence, -days)

        return sorted(candidates, key=topic_priority)[0]

    def recommend(self) -> list[dict]:
        """
        Returns a list of up to 2 recommendation dicts:
        [
          {
            "module":    Module,
            "topic":     Topic,
            "role":      "primary" | "revisit",
            "hours":     float,
            "rationale": str,
          }
        ]
        """
        budget = self.planner.recommended_today()
        if budget <= 0:
            return []

        scored = sorted(
            self.modules,
            key=lambda m: self._urgency_score(m),
            reverse=True
        )

        recommendations = []
        used_modules = set()

        # Primary: up to 60% of budget, min 0.5h
        for module in scored:
            topic = self._best_topic(module)
            if topic is None:
                continue
            primary_hours = round(min(budget * 0.6, budget), 1)
            primary_hours = max(primary_hours, 0.5)
            rationale = self._rationale(module)
            recommendations.append({
                "module":    module,
                "topic":     topic,
                "role":      "primary",
                "hours":     primary_hours,
                "rationale": rationale,
            })
            used_modules.add(module.name)
            break

        # Revisit: remaining budget from a different module, min 0.5h
        remaining = round(budget - (recommendations[0]["hours"] if recommendations else 0), 1)
        if remaining >= 0.5:
            for module in scored:
                if module.name in used_modules:
                    continue
                topic = self._best_topic(module)
                if topic is None:
                    continue
                rationale = self._rationale(module)
                recommendations.append({
                    "module":    module,
                    "topic":     topic,
                    "role":      "revisit",
                    "hours":     remaining,
                    "rationale": rationale,
                })
                break

        return recommendations

    def _rationale(self, module: Module) -> str:
        parts = []
        today = datetime.now()

        if module.ca.due_date and not module.ca_written:
            days = (module.ca.due_date - today).days
            if days <= 3:
                parts.append(f"CA in {days}d — urgent")
            elif days <= 7:
                parts.append(f"CA in {days}d")

        if module.final.due_date:
            days = (module.final.due_date - today).days
            if days <= 7:
                parts.append(f"final in {days}d")

        if module.assignment and not module.assignment.is_complete:
            days = module.assignment.days_until_due()
            if days is not None:
                if days <= 3:
                    parts.append(f"assignment due in {days}d — urgent")
                elif days <= 10:
                    parts.append(f"assignment due in {days}d")

        neglect = module.neglect_level()
        if neglect == "alert":
            days_ago = module.days_since_last_session()
            parts.append(f"not studied in {days_ago}d")
        elif neglect == "warn":
            days_ago = module.days_since_last_session()
            parts.append(f"last studied {days_ago}d ago")

        if module.average_confidence() <= 2:
            parts.append(f"avg confidence {module.average_confidence()}/4")

        parts.append(f"phase {module.current_phase} — {module.phase_label}")

        return "  |  ".join(parts) if parts else module.phase_label
