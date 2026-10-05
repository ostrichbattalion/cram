"""
cram/commands.py
All CLI command handlers. Each function takes parsed args and the loaded
module list, performs its action, saves, and returns a status message.
Nothing here knows about display formatting.
"""

from datetime import datetime
from models import Module, CONFIDENCE_LABELS
from database import (load_active, save_active, find_module, find_topic,
                      archive_module, set_date, advance_phase, mark_ca_written)
from scheduler import WeeklyPlanner
import json, os

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PLANNER_FILE = os.path.join(BASE_DIR, "data", "planner.json")


# ── Planner persistence ───────────────────────────────────────────────────────

def load_planner() -> WeeklyPlanner:
    if not os.path.exists(PLANNER_FILE):
        return WeeklyPlanner()
    with open(PLANNER_FILE) as f:
        return WeeklyPlanner.from_dict(json.load(f))


def save_planner(planner: WeeklyPlanner):
    os.makedirs(os.path.dirname(PLANNER_FILE), exist_ok=True)
    with open(PLANNER_FILE, "w") as f:
        json.dump(planner.to_dict(), f, indent=4)


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_log(module_query: str, topic_ref: str,
            hours: float, note: str = "") -> str:
    """
    Log a study session: --log "machine learning" 3 1.5
    """
    if hours <= 0:
        return "❌  Hours must be a positive number."

    modules = load_active()
    m = find_module(modules, module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    t = find_topic(m, topic_ref)
    if not t:
        return f"❌  Topic not found: '{topic_ref}' in {m.name}"

    t.log_session(hours, note)

    # Mirror into weekly planner
    planner = load_planner()
    planner.log_hours(hours)
    save_planner(planner)

    save_active(modules)
    return (f"✅  Logged {hours}h on {m.name} — "
            f"T{t.number}: {t.name}  "
            f"(total on topic: {t.hours_studied}h)")


def cmd_confidence(module_query: str, topic_ref: str, level: int) -> str:
    """
    Set topic confidence: --confidence "machine learning" 3 2
    """
    if level not in CONFIDENCE_LABELS:
        return f"❌  Confidence must be 1–4. Got {level}."

    modules = load_active()
    m = find_module(modules, module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    t = find_topic(m, topic_ref)
    if not t:
        return f"❌  Topic not found: '{topic_ref}' in {m.name}"

    old_level = t.confidence
    t.set_confidence(level)
    save_active(modules)

    direction = "▲" if level > old_level else ("▼" if level < old_level else "─")
    return (f"✅  {m.name} — T{t.number}: {t.name}\n"
            f"   Confidence: {old_level} {direction} {level}  "
            f"({CONFIDENCE_LABELS[level]})\n"
            f"   Hours at change: {t.hours_studied}h")


def cmd_assign(module_query: str, questions: int) -> str:
    """
    Mark assignment questions complete: --assign "stats" 2
    """
    if questions <= 0:
        return "❌  Question count must be positive."

    modules = load_active()
    m = find_module(modules, module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    if not m.assignment:
        return f"❌  {m.name} has no assignment configured."

    before = m.assignment.completed_q
    m.assignment.complete_questions(questions)
    after  = m.assignment.completed_q
    save_active(modules)

    status = "DONE ✅" if m.assignment.is_complete else (
        f"{after}/{m.assignment.total_q}q")
    return (f"✅  {m.name} assignment: {before} → {after}  ({status})")


def cmd_assign_hours(module_query: str, hours: float) -> str:
    """
    Log actual hours spent on an assignment, overriding the flat SAQA
    estimate (total_q x 2h) used until real hours are recorded:
    --assign-hours "programming" 6
    """
    if hours <= 0:
        return "❌  Hours must be a positive number."

    modules = load_active()
    m = find_module(modules, module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    if not m.assignment:
        return f"❌  {m.name} has no assignment configured."

    estimate = m.assignment.notional_hours
    m.assignment.log_hours(hours)
    save_active(modules)

    # Mirror into weekly planner, same as study sessions, since assignment
    # work is real time spent today too.
    planner = load_planner()
    planner.log_hours(hours)
    save_planner(planner)

    return (f"✅  {m.name} assignment hours: {m.assignment.hours_spent}h logged  "
            f"(SAQA estimate was {estimate}h — self-study budget now "
            f"{m.self_study_budget}h)")


def cmd_set_date(module_query: str, kind: str, date_str: str) -> str:
    """
    Set a CA or final exam date: --set-date "programming" ca 2026-06-10
    """
    if kind not in ("ca", "final"):
        return "❌  Kind must be 'ca' or 'final'."
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "❌  Date must be YYYY-MM-DD format."

    m = set_date(module_query, kind, date_str)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    label = "CA test" if kind == "ca" else "Final exam"
    return f"✅  {m.name} — {label} date set to {date_str}"


def cmd_phase(module_query: str, action: str = "next") -> str:
    """
    Advance module phase: --phase "machine learning" next
    Or set explicitly:   --phase "machine learning" 4
    """
    modules = load_active()
    m = find_module(modules, module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"

    if action == "next":
        if m.current_phase >= 5:
            return f"ℹ️   {m.name} is already at Phase 5 (Final Review)."
        old = m.current_phase
        m.current_phase += 1
        if m.current_phase >= 4:
            m.ca_written = True
        save_active(modules)
        return (f"✅  {m.name}: Phase {old} → {m.current_phase} "
                f"({m.phase_label})")
    elif action.isdigit():
        new_phase = int(action)
        if not 1 <= new_phase <= 5:
            return "❌  Phase must be 1–5."
        old = m.current_phase
        m.current_phase = new_phase
        if new_phase >= 4:
            m.ca_written = True
        save_active(modules)
        return (f"✅  {m.name}: Phase {old} → {m.current_phase} "
                f"({m.phase_label})")
    else:
        return "❌  Use 'next' or a phase number (1–5)."


def cmd_ca_written(module_query: str) -> str:
    """Mark the CA as written: --ca-written "big data" """
    m = mark_ca_written(module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"
    return (f"✅  {m.name} — CA marked as written. "
            f"Now in Phase {m.current_phase} ({m.phase_label})")


def cmd_day(state: str) -> str:
    """Set today's day state: --day off | light | active | intensive"""
    valid = ("off", "light", "active", "intensive")
    if state not in valid:
        return f"❌  State must be one of: {', '.join(valid)}"
    planner = load_planner()
    planner.set_day_state(state)
    save_planner(planner)
    labels = {
        "off":       "Rest day set. No recommendations today.",
        "light":     "Light day set. Budget capped at 1h.",
        "active":    "Active day set. Normal budget.",
        "intensive": "Intensive day set. Full hours logged count.",
    }
    return f"✅  {labels[state]}"


def cmd_archive(module_query: str) -> str:
    """Archive a module: --archive "information systems" """
    m = archive_module(module_query)
    if not m:
        return f"❌  Module not found: '{module_query}'"
    return f"📦  '{m.name}' archived."
