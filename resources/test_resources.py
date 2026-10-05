"""
Tests for the resources package. Run from the cram folder:
    python -m unittest resources.test_resources -v
Uses a temporary folder; never touches data/resources.json.
"""

import os
import tempfile
import unittest

from resources.models import ResourceIndex, parse_numbers, parse_status
from resources.scanner import scan, parse_module_dir


def _rec(path, name=None, size=100, module="Software Engineering 700", kind="reading"):
    return {"rel_path": path, "module": module, "code": "2026M1SEM700M",
            "kind": kind, "name": name or path.rsplit("/", 1)[-1], "size": size}


class TestReconcile(unittest.TestCase):
    def test_new_items_added(self):
        idx = ResourceIndex()
        r = idx.reconcile([_rec("SE/a.pdf"), _rec("SE/b.pdf", size=200)], "/root")
        self.assertEqual(len(r.added), 2)
        self.assertEqual(len(idx.items), 2)

    def test_moved_file_keeps_status(self):
        idx = ResourceIndex()
        idx.reconcile([_rec("SE/Class Resources/ch12.pdf")], "/root")
        idx.items["SE/Class Resources/ch12.pdf"].set_status("reviewed")
        r = idx.reconcile([_rec("SE/Prescribed Resources/ch12.pdf")], "/root")
        self.assertEqual(len(r.moved), 1)
        self.assertEqual(idx.items["SE/Prescribed Resources/ch12.pdf"].status, "reviewed")
        self.assertNotIn("SE/Class Resources/ch12.pdf", idx.items)

    def test_missing_file_flagged_not_deleted(self):
        idx = ResourceIndex()
        idx.reconcile([_rec("SE/a.pdf")], "/root")
        idx.items["SE/a.pdf"].set_status("started")
        r = idx.reconcile([], "/root")
        self.assertEqual(len(r.missing), 1)
        self.assertTrue(idx.items["SE/a.pdf"].missing)
        self.assertEqual(idx.items["SE/a.pdf"].status, "started")
        # comes back on a later scan
        idx.reconcile([_rec("SE/a.pdf")], "/root")
        self.assertFalse(idx.items["SE/a.pdf"].missing)

    def test_same_name_different_size_is_not_a_move(self):
        idx = ResourceIndex()
        idx.reconcile([_rec("SE/x/guide.pdf", size=100)], "/root")
        idx.items["SE/x/guide.pdf"].set_status("reviewed")
        r = idx.reconcile([_rec("SE/y/guide.pdf", size=999)], "/root")
        self.assertEqual(len(r.moved), 0)
        self.assertEqual(idx.items["SE/y/guide.pdf"].status, "new")


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_numbers("3", 8), [3])
        self.assertEqual(parse_numbers("1-3,6", 8), [1, 2, 3, 6])
        self.assertEqual(parse_numbers("5-2", 8), [2, 3, 4, 5])
        self.assertEqual(parse_numbers("all", 3), [1, 2, 3])
        self.assertIsNone(parse_numbers("9", 8))
        self.assertIsNone(parse_numbers("0", 8))
        self.assertIsNone(parse_numbers("two", 8))

    def test_status(self):
        self.assertEqual(parse_status("done"), "reviewed")
        self.assertEqual(parse_status("1"), "started")
        self.assertIsNone(parse_status("maybe"))

    def test_module_dir(self):
        self.assertEqual(parse_module_dir("Programming 731 (2026M1PRO731M)"),
                         ("Programming 731", "2026M1PRO731M"))
        self.assertIsNone(parse_module_dir("_Admin (timetables)"))
        self.assertIsNone(parse_module_dir("Random folder"))


class TestFindModule(unittest.TestCase):
    def setUp(self):
        self.idx = ResourceIndex()
        recs = [_rec(f"{m}/f.pdf", module=m, size=i)
                for i, m in enumerate(["Software Engineering 700", "Cyber Security 700",
                                       "Artificial Intelligence 700", "Human Computer Interaction 700"])]
        self.idx.reconcile(recs, "/root")

    def test_initials_beat_partial(self):
        self.assertEqual(self.idx.find_module("se"), "Software Engineering 700")
        self.assertEqual(self.idx.find_module("ai"), "Artificial Intelligence 700")
        self.assertEqual(self.idx.find_module("hci"), "Human Computer Interaction 700")

    def test_partial(self):
        self.assertEqual(self.idx.find_module("cyber"), "Cyber Security 700")
        self.assertIsNone(self.idx.find_module("biology"))


class TestScanner(unittest.TestCase):
    def test_layout(self):
        with tempfile.TemporaryDirectory() as root:
            mod = os.path.join(root, "Programming 731 (2026M1PRO731M)")
            files = {
                "Lectures/Workshop 2.mp4": "recording",
                "Class Resources/Topic 4/Intro.f136.mp4": "class",
                "Prescribed Resources/Additional Reading/Farrell 10th.pdf": "extra",
                "Prescribed Resources/Study Guide.pdf": "reading",
                "Past Papers/Exam.pdf": "past_paper",
            }
            skipped = ["Assignments/my work.zip", "Class Resources/Topic 4/Intro.f140.m4a",
                       "Class Resources/shortcut.lnk", "Table of Contents.txt"]
            for rel in list(files) + skipped:
                p = os.path.join(mod, *rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(b"x" * 10)
            os.makedirs(os.path.join(root, "_Admin"), exist_ok=True)
            found = {r["rel_path"].split("/", 1)[1]: r["kind"] for r in scan(root)}
            self.assertEqual(found, files)


class TestMarkByName(unittest.TestCase):
    """cmd_mark with a file-name fragment, against a temporary index file."""

    def setUp(self):
        import resources.commands as commands
        from resources.store import save_index, load_index
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "resources.json")
        idx = ResourceIndex()
        recs = []
        for i, m in enumerate(["Software Engineering 700", "Cyber Security 700"]):
            date = "2026-08-26" if i == 0 else "2026-08-22"
            for j, f in enumerate([f"Lectures/Workshop 1 - {date}.mp4",
                                   "Lectures/Earlier 2026 intake/Workshop 1 - 2026-03-14.mp4",
                                   "Lectures/Workshop 2 - 2026-09-12.mp4"]):
                recs.append(_rec(f"{m}/{f}", module=m, kind="recording", size=i * 10 + j + 1))
        idx.reconcile(recs, "/root")
        save_index(idx, path)
        # point the command layer at the temporary file
        self._orig = (commands.load_index, commands.save_index)
        commands.load_index = lambda: load_index(path)
        commands.save_index = lambda index: save_index(index, path)
        self.commands, self.load = commands, lambda: load_index(path)

    def tearDown(self):
        self.commands.load_index, self.commands.save_index = self._orig
        self.tmp.cleanup()

    def test_all_modules_by_name(self):
        self.commands.cmd_mark("all", "Workshop 1 - 2026-08", "done")
        done = sorted(r.rel_path for r in self.load().items.values() if r.status == "reviewed")
        self.assertEqual(done, ["Cyber Security 700/Lectures/Workshop 1 - 2026-08-22.mp4",
                                "Software Engineering 700/Lectures/Workshop 1 - 2026-08-26.mp4"])

    def test_all_with_numbers_refused(self):
        msg = self.commands.cmd_mark("all", "1", "done")
        self.assertIn("file name", msg)
        self.assertFalse(any(r.status == "reviewed" for r in self.load().items.values()))

    def test_no_match(self):
        self.assertIn("No items", self.commands.cmd_mark("all", "Workshop 9", "done"))

    def test_numbers_still_work(self):
        self.commands.cmd_mark("se", "1", "started")
        self.assertEqual(sum(r.status == "started" for r in self.load().items.values()), 1)


if __name__ == "__main__":
    unittest.main()
