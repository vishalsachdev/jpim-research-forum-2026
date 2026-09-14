#!/usr/bin/env python3
"""Compare two program datasets and check the newer one for structural problems.

Usage:
    scripts/diff_program.py OLD NEW [--old-label L] [--new-label L] [-o REPORT.md]

OLD and NEW may each be dist/data.js, a JSON file with the same shape, or a
program PDF (parsed with scripts/parse_program.py). Papers are matched by
paper ID. The report lists added, removed, moved and retitled papers,
presenter, co-author and discussant changes, and session track and chair
changes, followed by structural checks on NEW. Exits 1 when NEW fails a
structural check.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

REQUIRED = ["day", "date", "block", "slot", "start", "end", "room", "track", "chair",
            "title", "presenter", "discussant", "paperId"]
FIELD_KINDS = [("title", "retitled"), ("presenter", "presenter"),
               ("coauthors", "coauthors"), ("discussant", "discussant")]
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SECTIONS = [
    ("removed", "Removed papers"),
    ("added", "Added papers"),
    ("moved", "Moved papers"),
    ("retitled", "Retitled papers"),
    ("presenter", "Presenter changes"),
    ("coauthors", "Co-author changes"),
    ("discussant", "Discussant changes"),
    ("session-track", "Session track title changes"),
    ("session-chair", "Session chair changes"),
    ("session-added", "Sessions added"),
    ("session-removed", "Sessions removed"),
]


def load_dataset(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import parse_program
        return parse_program.parse_pdf(path)[0]
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("window."):
        text = text.split("=", 1)[1].strip()
    return json.loads(text.rstrip(";").strip())


def paper_key(paper):
    return paper.get("paperId") or "title:" + paper.get("title", "")


def placement(paper):
    return f"{paper['day']} {paper['start']}-{paper['end']}, {paper['slot']}, {paper['room']}"


def change(kind, paper, old, new):
    return {"kind": kind, "paperId": paper.get("paperId", ""), "title": paper.get("title", ""),
            "slot": paper.get("slot", ""), "room": paper.get("room", ""), "old": old, "new": new}


def compare(old, new):
    old_papers = {paper_key(p): p for p in old["papers"]}
    new_papers = {paper_key(p): p for p in new["papers"]}
    changes = []
    for key, paper in old_papers.items():
        if key not in new_papers:
            changes.append(change("removed", paper, placement(paper), None))
    for key, paper in new_papers.items():
        if key not in old_papers:
            changes.append(change("added", paper, None, placement(paper)))
    for key, paper in new_papers.items():
        before = old_papers.get(key)
        if before is None:
            continue
        if placement(before) != placement(paper):
            changes.append(change("moved", paper, placement(before), placement(paper)))
        for field, kind in FIELD_KINDS:
            if before.get(field, "") != paper.get(field, ""):
                changes.append(change(kind, paper, before.get(field, ""), paper.get(field, "")))

    def session_key(t):
        return (t["date"], t["block"], t["room"])

    old_sessions = {session_key(t): t for t in old.get("tracks", [])}
    new_sessions = {session_key(t): t for t in new.get("tracks", [])}
    for key, session in new_sessions.items():
        before = old_sessions.get(key)
        where = {"paperId": "", "title": "", "slot": session["block"], "room": session["room"]}
        if before is None:
            changes.append({"kind": "session-added", **where, "old": None, "new": session["track"]})
            continue
        for field in ("track", "chair"):
            if before[field] != session[field]:
                changes.append({"kind": f"session-{field}", **where,
                                "old": before[field], "new": session[field]})
    for key, session in old_sessions.items():
        if key not in new_sessions:
            changes.append({"kind": "session-removed", "paperId": "", "title": "",
                            "slot": session["block"], "room": session["room"],
                            "old": session["track"], "new": None})
    order = {kind: i for i, (kind, _) in enumerate(SECTIONS)}
    return sorted(changes, key=lambda c: order[c["kind"]])


def label(paper):
    ident = f"Paper {paper['paperId']}" if paper.get("paperId") else f"\"{paper.get('title', '')}\""
    return f"{ident} ({paper.get('slot', '?')}, {paper.get('room', '?')})"


def minutes(value):
    hours, mins = value.split(":")
    return int(hours) * 60 + int(mins)


def overlaps(a, b):
    return a[0] == b[0] and a[1] < b[2] and b[1] < a[2]


def check_structure(data):
    papers = data["papers"]
    issues = []

    counts = Counter(p.get("paperId") for p in papers if p.get("paperId"))
    for paper_id, count in counts.items():
        if count > 1:
            where = "; ".join(f"{p['slot']} {p['room']}" for p in papers if p.get("paperId") == paper_id)
            issues.append({"check": "duplicate-paper-id",
                           "detail": f"Paper {paper_id} appears {count} times: {where}"})

    for paper in papers:
        for field in REQUIRED:
            if not str(paper.get(field, "")).strip():
                issues.append({"check": "missing-field", "detail": f"{label(paper)}: {field} is empty"})

    timed = []
    for paper in papers:
        start, end = paper.get("start", ""), paper.get("end", "")
        if not (TIME_RE.match(start) and TIME_RE.match(end)):
            issues.append({"check": "invalid-time",
                           "detail": f"{label(paper)}: '{start}'-'{end}' is not HH:MM"})
        elif minutes(start) >= minutes(end):
            issues.append({"check": "invalid-time",
                           "detail": f"{label(paper)}: starts {start}, ends {end}"})
        else:
            timed.append((paper, (paper["date"], minutes(start), minutes(end))))

    by_room = defaultdict(list)
    for paper, span in timed:
        by_room[(paper["date"], paper["room"])].append((paper, span))
    for entries in by_room.values():
        for (a, span_a), (b, span_b) in combinations(entries, 2):
            if overlaps(span_a, span_b):
                issues.append({"check": "room-overlap",
                               "detail": f"{label(a)} and {label(b)} overlap in {a['room']}"})

    appearances = defaultdict(list)
    for paper, span in timed:
        for role in ("presenter", "discussant"):
            name = paper.get(role, "").strip()
            if name:
                appearances[name.casefold()].append((name, role, paper, span))
    for session in data.get("tracks", []):
        spans = [span for paper, span in timed
                 if (paper["date"], paper["block"], paper["room"]) ==
                 (session["date"], session["block"], session["room"])]
        name = session.get("chair", "").strip()
        if spans and name:
            chair_span = (spans[0][0], min(s[1] for s in spans), max(s[2] for s in spans))
            appearances[name.casefold()].append(
                (name, "chair", {"slot": session["block"], "room": session["room"], "paperId": ""},
                 chair_span))
    for entries in appearances.values():
        for (name, role_a, a, span_a), (_, role_b, b, span_b) in combinations(entries, 2):
            if a["room"] != b["room"] and overlaps(span_a, span_b):
                issues.append({"check": "person-conflict", "detail":
                               f"{name} is {role_a} in {a['room']} ({a['slot']}) and "
                               f"{role_b} in {b['room']} ({b['slot']}) at the same time"})
    return issues


def quote(value):
    return f"\"{value}\"" if value else "(none)"


def describe(c):
    ident = f"Paper {c['paperId']}" if c["paperId"] else "Session"
    if c["kind"] == "removed":
        return f"{ident}, {c['old']}: {quote(c['title'])}"
    if c["kind"] == "added":
        return f"{ident}, {c['new']}: {quote(c['title'])}"
    if c["kind"] == "moved":
        return f"{ident} {quote(c['title'])}: {c['old']} to {c['new']}"
    if c["kind"].startswith("session-"):
        return f"Block {c['slot']}, {c['room']}: {quote(c['old'])} to {quote(c['new'])}"
    return f"{ident} ({c['slot']}, {c['room']}): {quote(c['old'])} to {quote(c['new'])}"


def render_report(changes, issues, old_label, new_label):
    counts = Counter(c["kind"] for c in changes)
    lines = [f"# Program change report: {old_label} to {new_label}", ""]
    if changes:
        summary = ", ".join(f"{counts[kind]} {title.lower()}" for kind, title in SECTIONS if counts[kind])
        lines += [f"Summary: {summary}.", ""]
    else:
        lines += ["No differences in the parallel-session grid.", ""]
    for kind, title in SECTIONS:
        items = [c for c in changes if c["kind"] == kind]
        if items:
            lines.append(f"## {title}")
            lines += [f"- {describe(c)}" for c in items]
            lines.append("")
    lines.append(f"## Structural checks on {new_label}")
    if issues:
        lines += [f"- `{i['check']}`: {i['detail']}" for i in issues]
    else:
        lines.append("- Passed: no duplicate paper IDs, missing fields, invalid times, "
                     "room overlaps, or people in two rooms at once.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--old-label")
    parser.add_argument("--new-label")
    parser.add_argument("-o", "--output", type=Path, help="write the report here instead of stdout")
    args = parser.parse_args(argv)

    old, new = load_dataset(args.old), load_dataset(args.new)
    changes, issues = compare(old, new), check_structure(new)
    report = render_report(changes, issues, args.old_label or args.old.name, args.new_label or args.new.name)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
