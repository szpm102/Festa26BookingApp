(function () {
  const mapEl = document.getElementById("seat-map");
  const mapCaptionEl = document.getElementById("map-scale-caption");
  const countEl = document.getElementById("selected-count");
  const totalEl = document.getElementById("selected-total");
  const flashEl = document.getElementById("flash-area");
  const form = document.getElementById("booking-form");
  const payBtn = document.getElementById("pay-btn");

  let seats = [];
  let busy = false;

  function flash(message, type) {
    flashEl.innerHTML = `<div class="msg ${type}">${message}</div>`;
    setTimeout(() => { flashEl.innerHTML = ""; }, 6000);
  }

  const SVGNS = "http://www.w3.org/2000/svg";

  // Approximate real-world scale: 1 metre = 24px (sized to use the full width
  // of the booking card). Seats are placed directly on the closed-off road,
  // houses on one side, the fireworks field on the other - matching the
  // actual Andrijiet Street cross-section.
  //
  // The real seating plan is 5 sections placed side by side across the
  // street (A..E), each 10 seats wide and 6 rows deep, with an 80cm gap
  // between adjacent sections - not one continuous 60-wide row.
  const M = 24;
  const SEAT_W = 0.55 * M, SEAT_GAP = 0.12 * M;          // ~1m11 seat pitch incl. gap
  const ROW_H = 0.85 * M, ROW_GAP = 0.18 * M;             // ~1m03 per row incl. gap
  const SECTION_GAP = 0.8 * M;                            // 80cm gap between sections
  const MARGIN_X = 16, MARGIN_TOP = 4;
  const HOUSES_H = 3.2 * M, GAP_HOUSES_SEATS = 6;
  const ROAD_PAD = 20, GAP_SEATS_FIELD = 6; // extra top padding leaves room for the section labels
  const FIELD_H = 5.5 * M, BOTTOM_PAD = 18;

  function el(tag, attrs) {
    const node = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach((k) => node.setAttribute(k, attrs[k]));
    return node;
  }

  function render() {
    if (!seats.length) return;
    // Sections placed left to right in the order they come back from the
    // API (already section, row, number - see routes_api.py); rows drawn
    // top (nearest the houses) to bottom (nearest the field), so the row
    // closest to the fireworks field ends up numbered "1".
    const sections = [...new Set(seats.map((s) => s.section))].sort();
    const rows = [...new Set(seats.map((s) => s.row))].sort().reverse();
    const seatsPerSectionRow = Math.max(...seats.map((s) => s.number));

    const blockWidth = seatsPerSectionRow * SEAT_W + (seatsPerSectionRow - 1) * SEAT_GAP;
    const seatsWidth = sections.length * blockWidth + (sections.length - 1) * SECTION_GAP;
    const width = MARGIN_X * 2 + seatsWidth;
    const seatingHeight = rows.length * ROW_H + (rows.length - 1) * ROW_GAP;

    const housesY = MARGIN_TOP;
    const roadY = housesY + HOUSES_H + GAP_HOUSES_SEATS;
    const seatingY = roadY + ROAD_PAD;
    const roadH = ROAD_PAD * 2 + seatingHeight;
    const fieldY = roadY + roadH + GAP_SEATS_FIELD;
    const height = fieldY + FIELD_H + BOTTOM_PAD;

    const streetLengthM = (seatsWidth / M).toFixed(0);
    const rowsDepthM = (seatingHeight / M).toFixed(1);
    mapCaptionEl.textContent = `Approx. scale: ${sections.length} sections spanning ~${streetLengthM}m along the closed-off street, ${rows.length} rows deep (~${rowsDepthM}m) each.`;

    const sectionX = {};
    sections.forEach((sec, i) => { sectionX[sec] = MARGIN_X + i * (blockWidth + SECTION_GAP); });

    mapEl.innerHTML = "";
    const svg = el("svg", {
      viewBox: `0 0 ${width} ${height}`,
      width: Math.max(width, 700),
      class: "seatmap-svg",
      role: "img",
      "aria-label": "Seating map: houses, seats placed on the closed-off road, then the fireworks field",
    });

    // Houses (behind the seating, opposite the field)
    svg.appendChild(el("rect", { x: 0, y: housesY, width, height: HOUSES_H, class: "map-houses" }));
    const houseW = 42, houseGap = 6;
    for (let x = 4; x < width - 10; x += houseW + houseGap) {
      const w = Math.min(houseW, width - 10 - x);
      if (w < 16) break;
      svg.appendChild(el("rect", { x, y: housesY + HOUSES_H * 0.35, width: w, height: HOUSES_H * 0.65, class: "map-house-body" }));
      svg.appendChild(el("polygon", {
        points: `${x - 2},${housesY + HOUSES_H * 0.35} ${x + w / 2},${housesY + HOUSES_H * 0.05} ${x + w + 2},${housesY + HOUSES_H * 0.35}`,
        class: "map-house-roof",
      }));
    }
    const housesLabel = el("text", { x: width / 2, y: housesY + HOUSES_H + 12, class: "map-label map-label-dim" });
    housesLabel.textContent = "HOUSES — TRIQ ANDRIJIET";
    svg.appendChild(housesLabel);

    // Road surface, with seats placed directly on it
    svg.appendChild(el("rect", { x: 0, y: roadY, width, height: roadH, class: "map-road" }));
    svg.appendChild(el("line", { x1: 4, y1: roadY + 4, x2: width - 4, y2: roadY + 4, class: "map-road-edge" }));
    svg.appendChild(el("line", { x1: 4, y1: roadY + roadH - 4, x2: width - 4, y2: roadY + roadH - 4, class: "map-road-edge" }));

    // Section labels, one per block, spanning its full depth
    sections.forEach((sec) => {
      const label = el("text", {
        x: sectionX[sec] + blockWidth / 2, y: seatingY - 4,
        class: "map-section-label", "text-anchor": "middle",
      });
      label.textContent = "SECTION " + sec;
      svg.appendChild(label);
    });

    // Seats, row by row, each row spanning every section left to right
    rows.forEach((row, rowIndex) => {
      const y = seatingY + rowIndex * (ROW_H + ROW_GAP);

      seats
        .filter((s) => s.row === row)
        .sort((a, b) => a.number - b.number)
        .forEach((seat) => {
          const x = sectionX[seat.section] + (seat.number - 1) * (SEAT_W + SEAT_GAP);
          const rect = el("rect", {
            x, y, width: SEAT_W, height: ROW_H, rx: 2.5,
            class: `seat-shape status-${seat.status}`,
          });
          const title = el("title", {});
          title.textContent = `Seat ${seat.label}`;
          rect.appendChild(title);
          if (!["held", "booked", "disabled"].includes(seat.status)) {
            rect.addEventListener("click", () => onSeatClick(seat));
          }
          svg.appendChild(rect);
        });
    });

    // Field (fireworks launch site, opposite the houses)
    svg.appendChild(el("rect", { x: 0, y: fieldY, width, height: FIELD_H, class: "map-field" }));
    svg.appendChild(el("line", { x1: 0, y1: fieldY, x2: width, y2: fieldY, class: "map-field-boundary" }));
    const fieldLabel = el("text", { x: width / 2, y: fieldY + FIELD_H / 2 + 4, class: "map-label" });
    fieldLabel.textContent = "\u{1F386} FIREWORKS DISPLAY FIELD";
    svg.appendChild(fieldLabel);

    mapEl.appendChild(svg);

    const mine = seats.filter((s) => s.status === "held_mine");
    countEl.textContent = mine.length;
    totalEl.textContent = "€" + (mine.length * window.SEAT_PRICE).toFixed(2);
    payBtn.disabled = mine.length === 0;
  }

  async function loadSeats() {
    try {
      const res = await fetch("/api/seats");
      const data = await res.json();
      seats = data.seats;
      render();
    } catch (e) {
      // silent retry on next poll
    }
  }

  async function onSeatClick(seat) {
    if (busy) return;
    if (seat.status === "available") {
      busy = true;
      const res = await fetch("/api/hold", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seat_id: seat.id }),
      });
      const data = await res.json();
      if (data.seats) seats = data.seats;
      if (!data.ok) flash(data.error || "Could not hold that seat.", "error");
      render();
      busy = false;
    } else if (seat.status === "held_mine") {
      busy = true;
      const res = await fetch("/api/release", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seat_id: seat.id }),
      });
      const data = await res.json();
      if (data.seats) seats = data.seats;
      render();
      busy = false;
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    payBtn.disabled = true;
    payBtn.textContent = "Redirecting to payment...";
    const body = {
      name: document.getElementById("name").value,
      email: document.getElementById("email").value,
      phone: document.getElementById("phone").value,
    };
    try {
      const res = await fetch("/booking/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.ok) {
        window.location.href = data.checkout_url;
      } else {
        flash(data.error || "Something went wrong.", "error");
        payBtn.disabled = false;
        payBtn.textContent = "Proceed to Payment";
      }
    } catch (err) {
      flash("Network error, please try again.", "error");
      payBtn.disabled = false;
      payBtn.textContent = "Proceed to Payment";
    }
  });

  loadSeats();
  setInterval(loadSeats, 4000);
})();
