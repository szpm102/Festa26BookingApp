"""
Seat layout definition - the real, finalised seating plan for Andrijiet
Street, Munxar (source: SeatingPlanStructure.xlsx).

5 sections placed side by side across the closed-off street (A, B, C, D, E),
each 65cm-per-seat / 6.5m wide (10 seats across) and 6 rows deep (60 seats
per section), with an 80cm gap between adjacent sections. Seat labels are
section + a running 1-60 number within that section (e.g. "A1".."A60"),
matching the numbering in the spreadsheet exactly. Internally each seat also
records its row (1-6, depth within the section) and its position (1-10)
within that row, computed from the running number.

Only part of the plan is being opened for booking at first - see
FIRST_BATCH_LABELS below. The rest are seeded as `disabled` and can be
opened later from the admin dashboard (select the seats on the map, click
"Enable selected") once the committee is ready, without needing a code
change or a re-seed.
"""

SECTIONS = ["A", "B", "C", "D", "E"]
SEATS_PER_SECTION = 60
SEATS_PER_ROW = 10  # -> 6 rows deep per section (60 / 10)

SEAT_LAYOUT = []
for section in SECTIONS:
    for n in range(1, SEATS_PER_SECTION + 1):
        row_in_section = (n - 1) // SEATS_PER_ROW + 1  # 1..6, depth within the section
        seat_in_row = (n - 1) % SEATS_PER_ROW + 1  # 1..10, position within that row
        SEAT_LAYOUT.append({
            "section": section,
            "row": str(row_in_section),
            "number": seat_in_row,
            "label": f"{section}{n}",
        })

assert len(SEAT_LAYOUT) == 300, "Seat layout must total 300 seats"

# The first batch to open: all of sections A and B except their very back
# row (seats 51-60 in each, i.e. row 6) - 100 seats. Everything else (the
# back row of A/B, plus all of C, D, E - 200 seats) starts disabled.
FIRST_BATCH_LABELS = {
    f"{section}{n}"
    for section in ("A", "B")
    for n in range(1, 51)
}
assert len(FIRST_BATCH_LABELS) == 100
