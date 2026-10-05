"""
cram/display.py
All terminal rendering. Nothing here mutates models or touches the database.
Uses ANSI colour codes directly — no external dependencies required.
"""

from datetime import datetime
from models import (Module, Topic, CONFIDENCE_LABELS,
                    NEGLECT_WARN_DAYS, NEGLECT_ALERT_DAYS)
from scheduler import WeeklyPlanner, DailyRecommender

# ── ANSI colours ──────────────────────────────────────────────────────────────
R  = "\033[91m"   # red
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
P  = "\033[95m"   # purple
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white / bright
DIM= "\033[2m"    # dim
RST= "\033[0m"    # reset

BAR_WIDTH = 20


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _bar(percent: int, color: str = B) -> str:
    filled = min(percent, 100) // 5
    return f"{color}{'█' * filled}{DIM}{'─' * (BAR_WIDTH - filled)}{RST}"

def _confidence_pips(level: int) -> str:
    filled = "●" * level
    empty  = "○" * (4 - level)
    colors  = {1: R, 2: Y, 3: B, 4: G}
    return f"{colors.get(level, W)}{filled}{DIM}{empty}{RST}"

def _days_label(days: int | None, written: bool = False) -> str:
    if days is None:
        return f"{DIM}TBC{RST}"
    if written or days < 0:
        return f"{G}WRITTEN{RST}"
    if days == 0:
        return f"{R}TODAY{RST}"
    if days <= 2:
        return f"{R}{days}d{RST}"
    if days <= 7:
        return f"{Y}{days}d{RST}"
    return f"{days}d"

def _phase_color(phase: int) -> str:
    return {1: C, 2: B, 3: Y, 4: P, 5: G}.get(phase, W)

def _header(title: str, width: int = 62):
    print(f"\n{W}{'─' * width}{RST}")
    print(f"{W}  {title}{RST}")
    print(f"{W}{'─' * width}{RST}")

def _section(title: str, width: int = 62):
    print(f"\n{DIM}{'┄' * width}{RST}")
    print(f"{C}  {title}{RST}")


# ── Detailed view ─────────────────────────────────────────────────────────────

def print_detailed(modules: list[Module]):
    _header("CRAM  ─  Study Tracker")

    for m in modules:
        _print_module_detailed(m)

    print(f"\n{DIM}{'─' * 62}{RST}\n")


def _print_module_detailed(m: Module):
    phase_col  = _phase_color(m.current_phase)
    ca_days    = m.ca.days_until_due()
    final_days = m.final.days_until_due()

    # ── Module header ────────────────────────────────────────────────────────
    print(f"\n{phase_col}▶ {m.name.upper()}  {DIM}({m.code}  NQF{m.nqf_level}  {m.credits}cr){RST}")

    # Notional budget line
    pct = min(int(m.hours_studied / m.self_study_budget * 100), 100) if m.self_study_budget else 0
    bar = _bar(pct, phase_col)
    print(f"  Budget:  [{bar}] {pct:>3}%  "
          f"({m.hours_studied}/{m.self_study_budget}h self-study)")

    # Phase line
    print(f"  Phase:   {phase_col}{m.current_phase} — {m.phase_label}{RST}  "
          f"  CA: {_days_label(ca_days, m.ca_written)}  "
          f"  Final: {_days_label(final_days)}")

    # Burn-down
    rec = m.recommended_daily_hours()
    has_final = m.final.due_date is not None
    if rec is None:
        pass  # no sessions and no dates — nothing useful to show
    elif rec == 0:
        print(f"  Today:   {G}✓ budget exhausted — on track{RST}")
    else:
        if has_final:
            print(f"  Today:   {Y}⚡ {rec}h/day to finish by final{RST}")
        else:
            print(f"  Today:   {Y}⚡ {rec}h/day  {DIM}(est. — set final date for exact figure){RST}")

    # Assignment
    if m.assignment:
        a = m.assignment
        apct = a.percent_complete
        abar = _bar(apct, G if a.is_complete else Y)
        a_due = f"due {a.due_date_str}" if a.due_date_str else "due TBC"
        status = f"{G}DONE{RST}" if a.is_complete else a_due
        print(f"  Assign:  [{abar}] {apct:>3}%  "
              f"({a.completed_q}/{a.total_q}q)  {status}")

    # Topics
    if m.current_phase == 5:
        # Final Review: all topics active — both arcs need a second pass.
        final_topics = [t for t in m.topics if t.arc == "final"]
        ca_topics    = [t for t in m.topics if t.arc == "ca"]
        if final_topics:
            print(f"\n  {DIM}FINAL ARC TOPICS{RST}")
            for t in final_topics:
                _print_topic_line(t)
        if ca_topics:
            print(f"\n  {DIM}CA ARC TOPICS  {DIM}(second pass — all active){RST}")
            for t in ca_topics:
                _print_topic_line(t)
    else:
        arc_label = "final" if m.current_phase >= 4 else "ca"
        active_topics = [t for t in m.topics if t.arc == arc_label]
        other_topics  = [t for t in m.topics if t.arc != arc_label]

        if active_topics:
            arc_title = "FINAL ARC TOPICS" if arc_label == "final" else "CA ARC TOPICS"
            print(f"\n  {DIM}{arc_title}{RST}")
            for t in active_topics:
                _print_topic_line(t)

        if other_topics:
            other_title = "CA ARC (written)" if arc_label == "final" else "FINAL ARC"
            print(f"\n  {DIM}{other_title}{RST}")
            for t in other_topics:
                _print_topic_line(t, dim=True)


def _print_topic_line(t: Topic, dim: bool = False):
    prefix = DIM if dim else ""
    neglect = t.neglect_level()
    n_col   = R if neglect == "alert" else (Y if neglect == "warn" else "")

    days_ago = t.days_since_last_session()
    if days_ago is None:
        last = f"{DIM}no sessions{RST}"
    elif days_ago == 0:
        last = f"{G}today{RST}"
    else:
        last = f"{n_col}{days_ago}d ago{RST}"

    pips  = _confidence_pips(t.confidence)
    label = CONFIDENCE_LABELS[t.confidence]

    name_col = DIM if dim else W
    print(f"  {prefix}  T{t.number}  {name_col}{t.name[:38]:<38}{RST}  "
          f"{pips}  {t.hours_studied:>4.1f}h  {last}")


# ── Compact view ──────────────────────────────────────────────────────────────

def print_compact(modules: list[Module]):
    _header("CRAM  ─  Compact View")
    print(f"  {'Module':<28} {'Phase':<16} {'Progress':>10}  "
          f"{'CA':>6}  {'Final':>7}  {'Assign':>8}")
    print(f"  {DIM}{'─'*28}  {'─'*16}  {'─'*10}  {'─'*6}  {'─'*7}  {'─'*8}{RST}")

    for m in modules:
        phase_col = _phase_color(m.current_phase)
        pct = min(int(m.hours_studied / m.self_study_budget * 100), 100) if m.self_study_budget else 0
        ca_days    = m.ca.days_until_due()
        final_days = m.final.days_until_due()
        apct = m.assignment.percent_complete if m.assignment else 0

        name = m.name[:27]
        phase_str = f"{m.current_phase}─{m.phase_label[:12]}"

        print(f"  {phase_col}{name:<28}{RST}  "
              f"{phase_col}{phase_str:<16}{RST}  "
              f"{pct:>9}%  "
              f"{_days_label(ca_days, m.ca_written):>6}  "
              f"{_days_label(final_days):>7}  "
              f"{apct:>7}%")

    print(f"\n  {DIM}{'─' * 62}{RST}\n")


# ── Log view ──────────────────────────────────────────────────────────────────

def print_log(modules: list[Module], filter_module: str = None):
    """Print chronological study log grouped by week, newest first."""
    _header("CRAM  ─  Study Log")

    # Collect all sessions across all modules/topics
    all_sessions = []
    for m in modules:
        if filter_module and filter_module.lower() not in m.name.lower():
            continue
        for t in m.topics:
            for s in t.sessions:
                all_sessions.append({
                    "date":   s.date_str,
                    "hours":  s.hours,
                    "note":   s.note,
                    "topic":  t.name,
                    "module": m.name,
                    "confidence": t.confidence,
                })

    if not all_sessions:
        print(f"\n  {DIM}No sessions logged yet.{RST}\n")
        return

    # Sort newest first
    all_sessions.sort(key=lambda s: s["date"], reverse=True)

    # Group into ISO weeks
    def iso_week(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.isocalendar()[:2]  # (year, week)

    current_week = None
    week_total   = 0.0
    grand_total  = 0.0

    for s in all_sessions:
        week = iso_week(s["date"])
        if week != current_week:
            if current_week is not None:
                print(f"  {DIM}{'─'*58}{RST}")
                print(f"  {DIM}Week total: {week_total:.1f} hrs{RST}\n")
            current_week = week
            week_total = 0.0
            # Week label
            d = datetime.strptime(s["date"], "%Y-%m-%d")
            monday = d - __import__('datetime').timedelta(days=d.weekday())
            print(f"\n  {C}Week of {monday.strftime('%d %b %Y')}{RST}")
            print(f"  {DIM}{'─'*58}{RST}")

        date_fmt = datetime.strptime(s["date"], "%Y-%m-%d").strftime("%a %d %b")
        mod_short = s["module"][:22]
        top_short = s["topic"][:28]
        note_str  = f"  {DIM}{s['note'][:30]}{RST}" if s["note"] else ""
        conf_pip  = _confidence_pips(s["confidence"])

        print(f"  {date_fmt}  {B}{mod_short:<22}{RST}  "
              f"{top_short:<28}  {s['hours']:>4.1f}h  {conf_pip}{note_str}")

        week_total  += s["hours"]
        grand_total += s["hours"]

    # Final week footer
    print(f"  {DIM}{'─'*58}{RST}")
    print(f"  {DIM}Week total: {week_total:.1f} hrs{RST}")
    print(f"\n  {W}Total logged: {grand_total:.1f} hrs across "
          f"{len(all_sessions)} sessions{RST}\n")


# ── Today's plan ──────────────────────────────────────────────────────────────

def print_plan(modules: list[Module], planner: WeeklyPlanner):
    """Print today's recommended study plan."""
    recommender = DailyRecommender(modules, planner)
    recs        = recommender.recommend()
    today_str   = datetime.now().strftime("%A %d %B %Y")
    budget      = planner.recommended_today()
    logged      = planner.hours_logged_today()
    week_logged = planner.hours_logged_this_week()
    week_pool   = planner.weekly_pool()
    state       = planner.day_state()

    _header(f"CRAM  ─  Today's Plan  ─  {today_str}")

    state_col = {
        "off": R, "light": Y, "active": G, "intensive": P
    }.get(state, W)
    print(f"\n  Day state:   {state_col}{state.upper()}{RST}  "
          f"  Budget: {budget}h  "
          f"  Logged today: {logged}h")
    print(f"  Week:        {week_logged:.1f} / {week_pool:.1f}h  "
          f"  Remaining pool: {planner.remaining_pool():.1f}h")

    if not recs:
        if state == "off":
            print(f"\n  {G}Rest day — enjoy the break.{RST}\n")
        else:
            print(f"\n  {Y}No recommendations available. "
                  f"Check your module dates or log some sessions.{RST}\n")
        return

    print()
    for rec in recs:
        m     = rec["module"]
        t     = rec["topic"]
        role  = rec["role"].upper()
        role_col = W if rec["role"] == "primary" else DIM
        phase_col = _phase_color(m.current_phase)

        print(f"  {role_col}{role:<8}{RST}  "
              f"{phase_col}{m.name:<30}{RST}  {rec['hours']}h")
        print(f"           Topic {t.number}: {t.name[:48]}")
        print(f"           {DIM}{rec['rationale']}{RST}")
        print(f"           Confidence: {_confidence_pips(t.confidence)}  "
              f"  Hours on topic: {t.hours_studied}h")
        print()

    total_rec = sum(r["hours"] for r in recs)
    print(f"  {DIM}Total recommended: {total_rec}h{RST}\n")


# ── Archived view ─────────────────────────────────────────────────────────────

def print_archived(modules: list[Module]):
    if not modules:
        print(f"\n  {DIM}No archived modules.{RST}\n")
        return
    _header("CRAM  ─  Archived Modules")
    for m in modules:
        print(f"  {DIM}▶ {m.name}  ({m.code})  "
              f"{m.hours_studied}h logged  "
              f"Phase {m.current_phase}{RST}")
    print()
