"""Tests for scripts/parse_program.py.

Fixtures are single real pages of the organizer PDFs, extracted with
`pdftotext -bbox -f N -l N`:
  program-20260907-block1AM.bbox.html  (09-07 PDF, page 5, Saturday Block 1AM)
  program-20260914-block2PM.bbox.html  (09-14 PDF, page 11, Sunday Block 2PM)
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import parse_program  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

PAPER_KEYS = [
    "day", "date", "block", "type", "slot", "start", "end", "room", "track",
    "chair", "title", "presenter", "coauthors", "discussant", "paperId",
]
TRACK_KEYS = ["day", "date", "block", "room", "track", "chair"]


def load(name):
    return parse_program.parse_bbox_html((FIXTURES / name).read_text(encoding="utf-8"))


def find(papers, slot, room):
    matches = [p for p in papers if p["slot"] == slot and p["room"] == room]
    assert len(matches) == 1, f"{slot} {room}: {len(matches)} matches"
    return matches[0]


class Block1AM0907(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.unplaced = load("program-20260907-block1AM.bbox.html")
        cls.papers = cls.data["papers"]

    def test_first_paper_matches_published_row_exactly(self):
        self.assertEqual(self.papers[0], {
            "day": "Saturday", "date": "2026-10-10", "block": "1AM", "type": "Paper",
            "slot": "1AM.1", "start": "10:50", "end": "11:15",
            "room": "Capitol Ballroom North",
            "track": "Innovation Strategy and New Paradigms", "chair": "Luigi De Luca",
            "title": "When Rankings Backfire: Short-Horizon Accountability and the Hidden Costs of Innovation",
            "presenter": "Chenxi Qiao", "coauthors": "", "discussant": "Maximilian Bauer",
            "paperId": "22",
        })

    def test_paper_keys_keep_published_order(self):
        self.assertTrue(self.papers)
        for paper in self.papers:
            self.assertEqual(list(paper), PAPER_KEYS)

    def test_sixteen_papers_in_four_slots_by_four_rooms(self):
        self.assertEqual(len(self.papers), 16)
        self.assertEqual(
            sorted({(p["slot"], p["start"], p["end"]) for p in self.papers}),
            [("1AM.1", "10:50", "11:15"), ("1AM.2", "11:15", "11:40"),
             ("1AM.3", "11:40", "12:05"), ("1AM.4", "12:05", "12:30")],
        )

    def test_title_that_overflows_toward_next_column_stays_in_its_column(self):
        # In -layout text this title runs into column 2 with a single space.
        self.assertEqual(
            find(self.papers, "1AM.1", "Capitol Ballroom South")["title"],
            "Reconceptualizing Power in New Product Development Projects: "
            "A Structural Perspective on Intraorganizational Power",
        )

    def test_line_ending_hyphen_joins_without_space(self):
        self.assertEqual(
            find(self.papers, "1AM.4", "Capitol Ballroom South")["title"],
            "From Experimentation to Innovation: How Effectual Decision-Making "
            "drives Business Model Innovativeness through Serendipity",
        )

    def test_three_line_title(self):
        self.assertEqual(
            find(self.papers, "1AM.2", "Capitol Ballroom South")["title"],
            "Art Therapy-Empowered Smart Health Product Service Innovation for "
            "Emotional Regulation in Children with Autism Spectrum Disorder: "
            "A New Product Development Perspective",
        )

    def test_wrapped_coauthor_list_joins_with_space(self):
        self.assertEqual(
            find(self.papers, "1AM.2", "Capitol Ballroom South")["coauthors"],
            "Honghan Lin, Wenzhe Cun, Jiaqi Ge, Dengkai Chen, Chenqi Zhang",
        )

    def test_space_before_colon_is_removed(self):
        self.assertEqual(
            find(self.papers, "1AM.4", "Atlanta 2-3")["title"],
            "Orchestrating open innovation: Clusters as Meso-level governance mechanism",
        )

    def test_tracks_carry_room_title_and_chair(self):
        self.assertEqual(self.data["tracks"], [
            {"day": "Saturday", "date": "2026-10-10", "block": "1AM",
             "room": "Capitol Ballroom North",
             "track": "Innovation Strategy and New Paradigms", "chair": "Luigi De Luca"},
            {"day": "Saturday", "date": "2026-10-10", "block": "1AM",
             "room": "Capitol Ballroom South",
             "track": "New Product and Service Development", "chair": "Janell Townsend"},
            {"day": "Saturday", "date": "2026-10-10", "block": "1AM",
             "room": "Atlanta 2-3",
             "track": "Open Innovation and Innovation Ecosystems", "chair": "Micheal Stanko"},
            {"day": "Saturday", "date": "2026-10-10", "block": "1AM",
             "room": "Atlanta 4-5",
             "track": "Consumer and User Innovation and Adoption", "chair": "Subin Im"},
        ])
        for track in self.data["tracks"]:
            self.assertEqual(list(track), TRACK_KEYS)

    def test_every_word_in_the_grid_is_placed(self):
        self.assertEqual(self.unplaced, [])


class Block2PM0914(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.unplaced = load("program-20260914-block2PM.bbox.html")
        cls.papers = cls.data["papers"]

    def test_empty_cells_produce_no_paper(self):
        self.assertEqual(len(self.papers), 15)
        self.assertNotIn("2PM.5", {p["slot"] for p in self.papers})
        self.assertEqual(
            [p["room"] for p in self.papers if p["slot"] == "2PM.4"],
            ["Capitol Ballroom North", "Capitol Ballroom South", "Atlanta 2-3"],
        )

    def test_sunday_date(self):
        self.assertEqual({(p["day"], p["date"]) for p in self.papers},
                         {("Sunday", "2026-10-11")})

    def test_competition_cell_keeps_placement_as_paper_id(self):
        paper = find(self.papers, "2PM.1", "Atlanta 4-5")
        self.assertEqual(paper["paperId"], "PDMA Doctoral Dissertation Proposal Competition | 3rd Place")
        self.assertEqual(paper["presenter"], "Chen Han")
        self.assertEqual(paper["coauthors"], "")
        self.assertEqual(paper["discussant"], "Philipp Dahl")

    def test_revised_slot_content(self):
        paper = find(self.papers, "2PM.1", "Capitol Ballroom South")
        self.assertEqual(paper["paperId"], "118")
        self.assertEqual(paper["presenter"], "Rajani Ganesh Pillai")
        self.assertEqual(paper["coauthors"], "Elizabeth Crawford Jackson, Vishal Bindroo")
        self.assertEqual(paper["discussant"], "Jan Auernhammer")

    def test_multiline_track_titles(self):
        tracks = {t["room"]: t["track"] for t in self.data["tracks"]}
        self.assertEqual(tracks["Capitol Ballroom North"],
                         "Future Making + Innovation in the Era of Artificial Intelligence")
        self.assertEqual(tracks["Capitol Ballroom South"],
                         "Consumer and User Innovation and Adoption + Design Thinking and Design Innovation")

    def test_every_word_in_the_grid_is_placed(self):
        self.assertEqual(self.unplaced, [])


class Unplaced(unittest.TestCase):
    def test_word_between_label_column_and_first_room_is_reported(self):
        # Positive control for the "every word is placed" assertions above.
        page = (FIXTURES / "program-20260907-block1AM.bbox.html").read_text(encoding="utf-8")
        stray = '<word xMin="140.0" yMin="285.0" xMax="150.0" yMax="292.0">STRAY</word>\n</page>'
        _, unplaced = parse_program.parse_bbox_html(page.replace("</page>", stray, 1))
        self.assertEqual(len(unplaced), 1)
        self.assertIn("'STRAY'", unplaced[0])


class JsOutput(unittest.TestCase):
    def test_js_matches_published_data_js_format(self):
        data = {"tracks": [], "papers": [{"title": "Firm’s “quoted” Innovation？"}]}
        text = parse_program.to_js(data)
        self.assertEqual(
            text,
            'window.PROGRAM_DATA = {"tracks":[],"papers":[{"title":"Firm’s “quoted” Innovation？"}]};\n\n',
        )
        self.assertEqual(json.loads(text[len("window.PROGRAM_DATA = "):].rstrip().rstrip(";")), data)


if __name__ == "__main__":
    unittest.main()
