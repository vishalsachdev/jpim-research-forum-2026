"""Tests for scripts/diff_program.py.

Rows are real entries from dist/data.js (program dated 2026-09-07), trimmed
to the cases each test needs.
"""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import diff_program  # noqa: E402


def paper(**overrides):
    row = {
        "day": "Saturday", "date": "2026-10-10", "block": "1AM", "type": "Paper",
        "slot": "1AM.3", "start": "11:40", "end": "12:05",
        "room": "Capitol Ballroom South",
        "track": "New Product and Service Development", "chair": "Janell Townsend",
        "title": "Unpacking Agile. How Agile practices relate to performance in physical product development",
        "presenter": "Nicolò Cocchi", "coauthors": "Clio Dosi, Paola Giuri, Matteo Vignoli",
        "discussant": "Hang Zhao", "paperId": "42",
    }
    row.update(overrides)
    return row


SECOND = dict(
    slot="1AM.3", room="Capitol Ballroom North", track="Innovation Strategy and New Paradigms",
    chair="Luigi De Luca",
    title="Marshmallows in the Boardroom: Organizational Delay of Gratification and Innovation Persistence",
    presenter="John Jasionowicz", coauthors="David Maslach, Bruce Lamont, Ashok Bhandary",
    discussant="Mark Meckler", paperId="45",
)


def track(**overrides):
    row = {"day": "Saturday", "date": "2026-10-10", "block": "1AM",
           "room": "Capitol Ballroom South",
           "track": "New Product and Service Development", "chair": "Janell Townsend"}
    row.update(overrides)
    return row


def dataset(*papers, tracks=None):
    return {"tracks": tracks if tracks is not None else [track()], "papers": list(papers)}


def kinds(changes):
    return [c["kind"] for c in changes]


class Compare(unittest.TestCase):
    def test_identical_datasets_have_no_changes(self):
        data = dataset(paper(), paper(**SECOND))
        self.assertEqual(diff_program.compare(data, copy.deepcopy(data)), [])

    def test_added_and_removed_papers(self):
        old = dataset(paper(), paper(**SECOND))
        new = dataset(paper(), paper(paperId="84", title="From Signals to Systems", presenter="Honest Jimu"))
        changes = diff_program.compare(old, new)
        self.assertEqual(sorted(kinds(changes)), ["added", "removed"])
        added = next(c for c in changes if c["kind"] == "added")
        removed = next(c for c in changes if c["kind"] == "removed")
        self.assertEqual((added["paperId"], added["slot"]), ("84", "1AM.3"))
        self.assertEqual(removed["paperId"], "45")

    def test_moved_paper_reports_old_and_new_placement(self):
        old = dataset(paper())
        new = dataset(paper(slot="1AM.2", start="11:15", end="11:40"))
        changes = diff_program.compare(old, new)
        self.assertEqual(kinds(changes), ["moved"])
        self.assertEqual(changes[0]["old"], "Saturday 11:40-12:05, 1AM.3, Capitol Ballroom South")
        self.assertEqual(changes[0]["new"], "Saturday 11:15-11:40, 1AM.2, Capitol Ballroom South")

    def test_field_changes_on_the_same_paper(self):
        for field, kind in [("title", "retitled"), ("presenter", "presenter"),
                            ("coauthors", "coauthors"), ("discussant", "discussant")]:
            with self.subTest(field=field):
                changes = diff_program.compare(dataset(paper()), dataset(paper(**{field: "Changed"})))
                self.assertEqual(kinds(changes), [kind])
                self.assertEqual(changes[0]["paperId"], "42")
                self.assertEqual(changes[0]["new"], "Changed")

    def test_session_track_and_chair_changes(self):
        old = dataset(paper(), tracks=[track()])
        new = dataset(paper(), tracks=[track(track="Design Thinking", chair="Minu Kumar")])
        changes = diff_program.compare(old, new)
        self.assertEqual(sorted(kinds(changes)), ["session-chair", "session-track"])


class Structure(unittest.TestCase):
    def checks(self, data):
        return [issue["check"] for issue in diff_program.check_structure(data)]

    def test_clean_dataset_has_no_issues(self):
        self.assertEqual(self.checks(dataset(paper(), paper(**SECOND), tracks=[])), [])

    def test_duplicate_paper_id(self):
        self.assertIn("duplicate-paper-id",
                      self.checks(dataset(paper(), paper(**dict(SECOND, paperId="42")), tracks=[])))

    def test_person_in_two_rooms_at_once(self):
        data = dataset(paper(), paper(**dict(SECOND, discussant="Nicolò Cocchi")), tracks=[])
        issues = diff_program.check_structure(data)
        self.assertEqual([i["check"] for i in issues], ["person-conflict"])
        self.assertIn("Nicolò Cocchi", issues[0]["detail"])

    def test_room_double_booked(self):
        data = dataset(paper(), paper(**dict(SECOND, room="Capitol Ballroom South")), tracks=[])
        self.assertIn("room-overlap", self.checks(data))

    def test_missing_required_field(self):
        self.assertEqual(self.checks(dataset(paper(discussant=""), tracks=[])), ["missing-field"])

    def test_empty_coauthors_are_allowed(self):
        self.assertEqual(self.checks(dataset(paper(coauthors=""), tracks=[])), [])

    def test_invalid_time_format_and_order(self):
        self.assertEqual(self.checks(dataset(paper(start="11.40"), tracks=[])), ["invalid-time"])
        self.assertEqual(self.checks(dataset(paper(start="12:10"), tracks=[])), ["invalid-time"])


class Report(unittest.TestCase):
    def test_report_lists_changes_and_checks(self):
        old = dataset(paper(), paper(**SECOND))
        new = dataset(paper(slot="1AM.2", start="11:15", end="11:40"),
                      paper(**dict(SECOND, paperId="42")))
        text = diff_program.render_report(
            diff_program.compare(old, new), diff_program.check_structure(new),
            old_label="2026-09-07", new_label="2026-09-14")
        self.assertIn("2026-09-07", text)
        self.assertIn("Moved", text)
        self.assertIn("Paper 42", text)
        self.assertIn("duplicate-paper-id", text)
        self.assertNotIn("—", text)  # no em-dashes in user-facing text

    def test_load_dataset_reads_data_js_and_json(self):
        data = dataset(paper())
        with tempfile.TemporaryDirectory() as tmp:
            js = Path(tmp) / "data.js"
            js.write_text("window.PROGRAM_DATA = " + __import__("json").dumps(data) + ";\n", encoding="utf-8")
            as_json = Path(tmp) / "data.json"
            as_json.write_text(__import__("json").dumps(data), encoding="utf-8")
            self.assertEqual(diff_program.load_dataset(js), data)
            self.assertEqual(diff_program.load_dataset(as_json), data)


if __name__ == "__main__":
    unittest.main()
