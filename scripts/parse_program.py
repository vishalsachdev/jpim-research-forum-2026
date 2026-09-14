#!/usr/bin/env python3
"""Parse a JPIM Research Forum program PDF into the PROGRAM_DATA shape of dist/data.js.

Usage:
    scripts/parse_program.py sources/JPIM-RF-2026-Program-YYYYMMDD.pdf [--format js|json] [-o OUT]

The parallel-session pages are a grid: one column per room, one row group per
slot. `pdftotext -layout` flattens that grid into fixed-width text in which a
long title can run into the next room's column with a single space, so this
script reads word boxes from `pdftotext -bbox` instead and assigns every word
to a column by its x position and to a field by its y position.

Only the "(Block ...) | Parallel Sessions" pages are parsed. Plenaries, breaks
and the social dinner live in dist/special.js and are maintained by hand.
Words inside a session grid that cannot be assigned to a cell are reported on
stderr so nothing in the PDF is dropped silently.
"""

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

DAY_DATES = {"Saturday": "2026-10-10", "Sunday": "2026-10-11"}
PAPER_FIELDS = {
    "Paper Title": "title",
    "Presenter": "presenter",
    "Co-Authors": "coauthors",
    "Discussant": "discussant",
    "ID Paper": "paperId",
}
SESSION_FIELDS = {"Track Title": "track", "Track Chair": "chair"}

PAGE_RE = re.compile(r"<page\b[^>]*>(.*?)</page>", re.S)
WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
BLOCK_TITLE_RE = re.compile(r"\b(Saturday|Sunday) \w+ \(Block (\w+)\) \| Parallel Sessions")
TIME_RE = re.compile(r"^h(\d\d)\.(\d\d)-(\d\d)\.(\d\d)$")

LINE_TOLERANCE = 1.5   # points; words on one visual line share yMin
COLUMN_GAP = 15        # points between words that separates two room names


class Word(NamedTuple):
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def page_words(page_html):
    return [Word(float(a), float(b), float(c), float(d), html.unescape(t))
            for a, b, c, d, t in WORD_RE.findall(page_html)]


def group_lines(words):
    """Group words into visual lines, top to bottom, each sorted left to right."""
    lines = []
    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        if lines and abs(lines[-1][0].y0 - word.y0) <= LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def join_cell(words):
    text = ""
    for line in group_lines(words):
        part = " ".join(w.text for w in line)
        if text.endswith("-") and not text.endswith(" -"):
            text += part
        elif text:
            text += " " + part
        else:
            text = part
    return normalize(text)


def normalize(text):
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r" ([:;,])", r"\1", text)


def hhmm(hours, minutes):
    return f"{hours}:{minutes}"


def parse_session_page(words, page_number, unplaced):
    title_line = " ".join(w.text for w in sorted(words, key=lambda w: (round(w.y0), w.x0)))
    match = BLOCK_TITLE_RE.search(title_line)
    if not match:
        return None
    day, block = match.groups()
    date = DAY_DATES[day]

    room_label = next(w for w in words if w.text == "Room")
    label_x = room_label.x0

    room_words = sorted((w for w in words
                         if abs(w.y0 - room_label.y0) <= LINE_TOLERANCE and w.x0 > room_label.x1),
                        key=lambda w: w.x0)
    rooms, col_starts = [], []
    for word in room_words:
        if rooms and word.x0 - room_words[room_words.index(word) - 1].x1 <= COLUMN_GAP:
            rooms[-1] += " " + word.text
        else:
            rooms.append(word.text)
            col_starts.append(word.x0)

    def column_of(word):
        column = None
        for i, start in enumerate(col_starts):
            if word.x0 >= start - 1:
                column = i
        return column

    # Classify each visual line of the grid: label rows (x near the label
    # column) and time rows (slot or break times in the far-left column).
    grid = [w for w in words if w.y0 >= room_label.y0 - LINE_TOLERANCE]
    label_rows, slot_rows, anchors = [], [], []
    meta_ids = set()
    for line in group_lines(grid):
        meta = [w for w in line if w.x0 < label_x - 2]
        label = [w for w in line if label_x - 2 <= w.x0 < col_starts[0] - 5]
        label_text = " ".join(w.text for w in label)
        time = next((w for w in meta if TIME_RE.match(w.text)), None)
        y = line[0].y0
        if label_text in PAPER_FIELDS or label_text in SESSION_FIELDS or label_text == "Room":
            label_rows.append((y, label_text))
            meta_ids.update(id(w) for w in label)
            anchors.append(y)
        if time:
            anchors.append(y)
            meta_ids.update(id(w) for w in meta)
            texts = [w.text for w in meta]
            if "Slot" in texts:
                h1, m1, h2, m2 = TIME_RE.match(time.text).groups()
                slot_id = texts[texts.index("Slot") + 1]
                slot_rows.append((y, slot_id, hhmm(h1, m1), hhmm(h2, m2)))
    anchors = sorted(set(round(a, 1) for a in anchors))
    grid_end = anchors[-1] - LINE_TOLERANCE  # the break row after the last slot

    # Collect words per (label row, column).
    cells = {}
    placed = set(meta_ids) | {id(w) for w in room_words} | {id(room_label)}
    for y, label_text in label_rows:
        if label_text == "Room":
            continue
        later = [a for a in anchors if a > y + LINE_TOLERANCE]
        band_end = later[0] - LINE_TOLERANCE if later else float("inf")
        slot = None
        for slot_row in slot_rows:
            if slot_row[0] <= y + LINE_TOLERANCE:
                slot = slot_row
        for word in grid:
            if y - LINE_TOLERANCE <= word.y0 < band_end and id(word) not in placed:
                column = column_of(word)
                if column is None:
                    continue
                key = (slot[1] if slot and label_text in PAPER_FIELDS else None, label_text, column)
                cells.setdefault(key, []).append(word)
                placed.add(id(word))

    for word in grid:
        if id(word) not in placed and word.y0 < grid_end:
            unplaced.append(f"page {page_number}: {word.text!r} at x={word.x0:.1f} y={word.y0:.1f}")

    def cell(slot_id, label_text, column):
        return join_cell(cells.get((slot_id, label_text, column), []))

    tracks = [{
        "day": day, "date": date, "block": block, "room": room,
        "track": cell(None, "Track Title", i), "chair": cell(None, "Track Chair", i),
    } for i, room in enumerate(rooms)]

    papers = []
    for _, slot_id, start, end in slot_rows:
        for i, room in enumerate(rooms):
            fields = {name: cell(slot_id, label_text, i) for label_text, name in PAPER_FIELDS.items()}
            if not any(fields.values()):
                continue
            papers.append({
                "day": day, "date": date, "block": block, "type": "Paper",
                "slot": slot_id, "start": start, "end": end, "room": room,
                "track": tracks[i]["track"], "chair": tracks[i]["chair"],
                "title": fields["title"], "presenter": fields["presenter"],
                "coauthors": fields["coauthors"], "discussant": fields["discussant"],
                "paperId": fields["paperId"],
            })
    return tracks, papers


def parse_bbox_html(text):
    """Return (data, unplaced) for `pdftotext -bbox` output of one or more pages."""
    data = {"tracks": [], "papers": []}
    unplaced = []
    for number, page in enumerate(PAGE_RE.findall(text), start=1):
        parsed = parse_session_page(page_words(page), number, unplaced)
        if parsed:
            data["tracks"].extend(parsed[0])
            data["papers"].extend(parsed[1])
    return data, unplaced


def pdftotext_bbox(pdf_path):
    binary = shutil.which("pdftotext") or "/opt/homebrew/bin/pdftotext"
    result = subprocess.run([binary, "-bbox", str(pdf_path), "-"],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout


def parse_pdf(pdf_path):
    return parse_bbox_html(pdftotext_bbox(pdf_path))


def to_js(data):
    return "window.PROGRAM_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--format", choices=["js", "json"], default="js")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)

    data, unplaced = parse_pdf(args.pdf)
    if not data["papers"]:
        print(f"error: no parallel-session pages found in {args.pdf}", file=sys.stderr)
        return 1
    out = to_js(data) if args.format == "js" else json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    blocks = sorted({p["block"] for p in data["papers"]}, key=lambda b: [p["block"] for p in data["papers"]].index(b))
    print(f"{args.pdf.name}: {len(data['tracks'])} sessions, {len(data['papers'])} papers "
          f"in blocks {', '.join(blocks)}", file=sys.stderr)
    for line in unplaced:
        print(f"unplaced: {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
