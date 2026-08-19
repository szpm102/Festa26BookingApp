"""
Seat layout definition.

PLACEHOLDER LAYOUT: 5 rows (A-E) x 60 seats = 300 seats, single "Main" viewing
section. This was generated generically because no venue seating chart was
available yet. Once the real seating plan for Andrijiet Street, Munxar is
provided, replace SEAT_LAYOUT below with the actual sections/rows/seat counts
and re-run seed.py (it will not duplicate existing seats, only add new ones -
review/clear the seats table first if the layout changes significantly).
"""

import string

SEAT_LAYOUT = []

ROWS = list(string.ascii_uppercase[:5])  # A..E
SEATS_PER_ROW = 60

for row in ROWS:
    for num in range(1, SEATS_PER_ROW + 1):
        SEAT_LAYOUT.append({
            "section": "Main",
            "row": row,
            "number": num,
            "label": f"{row}{num}",
        })

assert len(SEAT_LAYOUT) == 300, "Seat layout must total 300 seats"
