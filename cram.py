"""
cram.py — entry point
Usage: python cram.py [command] [options]
"""

import argparse
import sys
from database import load_active, load_archived
from display  import (print_detailed, print_compact, print_log,
                      print_plan, print_archived, print_assignments)
from commands import (cmd_log, cmd_confidence, cmd_assign, cmd_assign_hours,
                      cmd_set_date, cmd_phase, cmd_ca_written, cmd_day,
                      cmd_archive, load_planner)
import resources                                   # course-content feature (optional)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cram",
        description="Study tracker grounded in SAQA notional hours.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # ── Views ─────────────────────────────────────────────────────────────────
    p.add_argument("--compact",  action="store_true",
                   help="Compact one-line-per-module view")
    p.add_argument("--log",      nargs="?", const="", metavar="MODULE",
                   help="Study log view (optionally filter by module name)")
    p.add_argument("--plan",     action="store_true",
                   help="Today's recommended study plan")
    p.add_argument("--archived", action="store_true",
                   help="Show archived modules")
    p.add_argument("--assignments", action="store_true",
                   help="Assignments-only view: progress and days until due")

    # ── Session logging ───────────────────────────────────────────────────────
    p.add_argument("--log-session", nargs=3,
                   metavar=("MODULE", "TOPIC", "HOURS"),
                   help='Log a study session\n'
                        'e.g. --log-session "machine learning" 3 1.5')
    p.add_argument("--note", default="",
                   help="Optional note for the session being logged")

    # ── Confidence ────────────────────────────────────────────────────────────
    p.add_argument("--confidence", nargs=3,
                   metavar=("MODULE", "TOPIC", "LEVEL"),
                   help='Set topic confidence (1–4)\n'
                        'e.g. --confidence "machine learning" 3 2')

    # ── Assignment ────────────────────────────────────────────────────────────
    p.add_argument("--assign", nargs=2,
                   metavar=("MODULE", "QUESTIONS"),
                   help='Mark assignment questions complete\n'
                        'e.g. --assign "stats" 2')
    p.add_argument("--assign-hours", nargs=2,
                   metavar=("MODULE", "HOURS"),
                   help='Log actual hours spent on an assignment, overriding\n'
                        'the flat SAQA estimate (total_q x 2h)\n'
                        'e.g. --assign-hours "programming" 6')

    # ── Dates ─────────────────────────────────────────────────────────────────
    p.add_argument("--set-date", nargs=3,
                   metavar=("MODULE", "KIND", "DATE"),
                   help='Set ca or final date (YYYY-MM-DD)\n'
                        'e.g. --set-date "programming" final 2026-06-20')

    # ── Phase ─────────────────────────────────────────────────────────────────
    p.add_argument("--phase", nargs=2,
                   metavar=("MODULE", "ACTION"),
                   help='Advance or set study phase\n'
                        'e.g. --phase "stats" next\n'
                        '     --phase "stats" 4')

    # ── CA written ────────────────────────────────────────────────────────────
    p.add_argument("--ca-written", metavar="MODULE",
                   help='Mark CA test as written\n'
                        'e.g. --ca-written "big data"')

    # ── Day state ─────────────────────────────────────────────────────────────
    p.add_argument("--day", metavar="STATE",
                   help='Set today\'s day state: off | light | active | intensive')

    # ── Archive ───────────────────────────────────────────────────────────────
    p.add_argument("--archive", metavar="MODULE",
                   help='Archive a module\n'
                        'e.g. --archive "information systems"')

    resources.register_args(p)                     # --res* flags

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if resources.handle(args):                     # --res* commands are self-contained
        return

    # ── Mutation commands (run first, then fall through to display) ───────────

    if args.log_session:
        module, topic, hours_str = args.log_session
        try:
            hours = float(hours_str)
        except ValueError:
            print("❌  Hours must be a number.")
            sys.exit(1)
        print(cmd_log(module, topic, hours, note=args.note))

    if args.confidence:
        module, topic, level_str = args.confidence
        try:
            level = int(level_str)
        except ValueError:
            print("❌  Confidence level must be an integer 1–4.")
            sys.exit(1)
        print(cmd_confidence(module, topic, level))

    if args.assign:
        module, q_str = args.assign
        try:
            questions = int(q_str)
        except ValueError:
            print("❌  Question count must be an integer.")
            sys.exit(1)
        print(cmd_assign(module, questions))

    if args.assign_hours:
        module, hours_str = args.assign_hours
        try:
            hours = float(hours_str)
        except ValueError:
            print("❌  Hours must be a number.")
            sys.exit(1)
        print(cmd_assign_hours(module, hours))

    if args.set_date:
        module, kind, date_str = args.set_date
        print(cmd_set_date(module, kind, date_str))

    if args.phase:
        module, action = args.phase
        print(cmd_phase(module, action))

    if args.ca_written:
        print(cmd_ca_written(args.ca_written))

    if args.day:
        print(cmd_day(args.day))

    if args.archive:
        print(cmd_archive(args.archive))

    # ── View commands ─────────────────────────────────────────────────────────

    # If any mutation ran, default to showing the detailed view after,
    # unless a specific view was requested
    any_mutation = any([
        args.log_session, args.confidence, args.assign, args.assign_hours,
        args.set_date, args.phase, args.ca_written,
        args.day, args.archive,
    ])

    if args.archived:
        print_archived(load_archived())
        return

    if args.assignments:
        modules = load_active()
        print_assignments(modules)
        return

    if args.log is not None:
        modules = load_active()
        print_log(modules, filter_module=args.log if args.log else None)
        return

    if args.plan:
        modules = load_active()
        planner = load_planner()
        print_plan(modules, planner)
        return

    if args.compact:
        modules = load_active()
        print_compact(modules)
        return

    # Default: detailed view
    modules = load_active()
    print_detailed(modules)


if __name__ == "__main__":
    main()
