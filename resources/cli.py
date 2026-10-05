"""
cram/resources/cli.py
The only surface cram.py touches. Two functions:

    register_args(parser)  adds the --res* flags to cram's argparse parser
    handle(args) -> bool   runs any --res* command; True means "I handled the
                           view, cram.py should return without its own output"
"""

import argparse

from .commands import cmd_scan, cmd_mark, cmd_open
from .store import load_index
from .display import print_summary, print_module, print_todo, print_no_index


def register_args(p: argparse.ArgumentParser):
    g = p.add_argument_group("course content (resources)")
    g.add_argument("--res", nargs="?", const="", metavar="MODULE",
                   help="Course content view: all modules, or one module's\n"
                        "numbered list of recordings, slides, papers, reading\n"
                        'e.g. --res  |  --res "software"')
    g.add_argument("--res-todo", action="store_true",
                   help="Everything not yet reviewed, across all modules")
    g.add_argument("--res-scan", nargs="?", const="", metavar="FOLDER",
                   help="Scan your semester folder for content (path is\n"
                        "remembered; later runs need no path)\n"
                        'e.g. --res-scan "C:\\...\\Semester 1"')
    g.add_argument("--res-mark", nargs=3, metavar=("MODULE", "ITEMS", "STATUS"),
                   help="Set review status: new | started | done\n"
                        'e.g. --res-mark "software" 3 done\n'
                        '     --res-mark "hci" 1-9 started\n'
                        'ITEMS can also be part of a file name, and MODULE\n'
                        'can be "all":\n'
                        '     --res-mark all "Workshop 1 - 2026-08" done')
    g.add_argument("--res-open", nargs=2, metavar=("MODULE", "ITEM"),
                   help="Open a resource; marks it started if new\n"
                        'e.g. --res-open "ai" 2')


def handle(args) -> bool:
    used = (args.res is not None or args.res_todo or args.res_scan is not None
            or args.res_mark or args.res_open)
    if not used:
        return False

    # Mutations first, mirroring cram.py
    module_after = None
    if args.res_scan is not None:
        print(cmd_scan(args.res_scan or None))
    if args.res_mark:
        module, items, status = args.res_mark
        print(cmd_mark(module, items, status))
        module_after = None if module.lower().strip() == "all" else module
    if args.res_open:
        module, item = args.res_open
        print(cmd_open(module, item))
        return True                 # opening a file needs no view after it

    # Then the view
    index = load_index()
    if not index.items:
        print_no_index()
        return True

    if args.res_todo:
        print_todo(index)
        return True

    target = args.res if args.res else module_after
    if target:
        name = index.find_module(target)
        if name:
            print_module(index, name)
        else:
            print(f"❌  Module not found: '{target}'")
        return True

    print_summary(index)
    return True
