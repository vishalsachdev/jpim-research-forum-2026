# Architecture of participation

The program should be useful before, during, and after the forum while keeping the official schedule trustworthy. The simplest model is a four-step contribution ladder with organizer review at the point where public information changes.

## 1. Browse and personalize

Every attendee can search, filter, save sessions, share a stable session link, and add events to common calendar clients without creating an account. An optional personal itinerary export could extend this later. These create value immediately without collecting attendee data.

## 2. Report and enrich

Low-friction issue forms give each group a clear path:

- **Attendees** report typos, room conflicts, accessibility issues, and useful feature ideas.
- **Presenters and co-authors** claim their listing by supplying a verified Google Scholar URL and optional paper, slides, code, data, or professional-profile links.
- **Organizers** attach a revised program PDF or describe an authoritative schedule change.

The site links directly to the issue chooser. Each form collects structured information, so contributors do not need to understand the code or data format.

## 3. Review and steward

Organizers remain the authority for names, titles, rooms, and times. A small label workflow keeps the queue legible:

1. `needs-source` — a schedule claim needs an organizer-provided source.
2. `needs-identity-check` — a profile or author match needs confirmation.
3. `ready-for-update` — the requested change is sufficiently verified.
4. `published` — the change is live and included in the changelog.

Attendees can discuss and improve requests, but an organizer or designated maintainer approves schedule changes. Feature improvements can use ordinary pull-request review.

## 4. Build and reuse

Technical contributors can improve search, accessibility, mobile behavior, data validation, or exports. Keep the underlying program data structured and dependency-free so it can later support printed agendas, displays, email reminders, or a conference chatbot without maintaining separate copies.

## AI-assisted update workflow

AI should prepare changes and evidence; it should not silently rewrite the official schedule.

### Revised PDF intake

When an organizer attaches a new PDF, an automated job can:

1. extract sessions, people, rooms, times, and paper IDs into a proposed dataset;
2. compare it with the currently published data;
3. flag additions, deletions, moved sessions, spelling changes, and ambiguous cells;
4. run structural checks for duplicate paper IDs, presenter conflicts, overlapping room assignments, missing fields, and invalid times;
5. open a pull request containing the proposed update and a human-readable change report.

An organizer reviews and merges the pull request. Publication should happen only after the structured checks pass.

### Identity and profile assistance

For names without a verified profile, AI can propose candidate Google Scholar profiles using name, affiliation, paper title, and co-author overlap. Because names are ambiguous, the system should record a direct profile URL only after presenter or organizer confirmation. Until then, the site should link to Google Scholar's author search for that name.

### Issue triage

AI can label incoming issues, identify the affected session, request missing evidence, detect duplicates, and draft the corresponding data change. Program updates should always remain in a review queue; feature requests can be summarized and grouped by attendee need.

### Release and communication

After an approved merge, automation can rebuild the site, publish it, comment on the issue with the live result, and generate a concise changelog. For time-sensitive changes, the same structured diff could later feed email, Slack, or calendar notifications without re-entering the update.

## Recommended rollout

1. **Now:** issue forms, contribution guide, Scholar search links, calendar export, stable session URLs, and organizer review labels.
2. **Next:** verified Scholar/profile mapping and personal itinerary export.
3. **Then:** PDF-to-pull-request automation with validation and a visible changelog.
4. **Later:** opt-in notifications and reusable program data for displays or assistants.
