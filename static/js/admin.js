(function () {
  const mapEl = document.getElementById("seat-map");
  const countEl = document.getElementById("selected-count");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  let seats = [];
  let selected = new Set();

  function headers() {
    return { "Content-Type": "application/json", "X-CSRFToken": csrfToken };
  }

  function render() {
    // Group by section first, then by row within that section - 5 blocks
    // (A..E) side by side in the real venue, each 6 rows deep, not one
    // continuous row spanning all sections.
    const bySection = {};
    seats.forEach((s) => {
      bySection[s.section] = bySection[s.section] || {};
      bySection[s.section][s.row] = bySection[s.section][s.row] || [];
      bySection[s.section][s.row].push(s);
    });
    const sections = Object.keys(bySection).sort();
    mapEl.innerHTML = "";
    sections.forEach((section) => {
      const sectionHeading = document.createElement("div");
      sectionHeading.className = "seat-section-heading";
      sectionHeading.textContent = "Section " + section;
      mapEl.appendChild(sectionHeading);

      const rows = Object.keys(bySection[section]).sort();
      rows.forEach((row) => {
        const rowDiv = document.createElement("div");
        rowDiv.className = "seat-row";
        const label = document.createElement("div");
        label.className = "row-label";
        label.textContent = row;
        rowDiv.appendChild(label);

        bySection[section][row]
          .sort((a, b) => a.number - b.number)
          .forEach((seat) => {
            const btn = document.createElement("button");
            let cls = `seat status-${seat.status}`;
            if (selected.has(seat.id)) cls += " selected";
            btn.className = cls;
            btn.textContent = seat.number;
            btn.title = seat.status === "booked"
              ? `${seat.label} - ${seat.attendee_name || ""} (${seat.reference || ""})`
              : `Seat ${seat.label}`;
            btn.addEventListener("click", () => onSeatClick(seat));
            rowDiv.appendChild(btn);
          });
        mapEl.appendChild(rowDiv);
      });
    });
    countEl.textContent = selected.size;
  }

  async function onSeatClick(seat) {
    if (seat.status === "booked") {
      const who = seat.attendee_name ? ` (booked by ${seat.attendee_name}, ref ${seat.reference})` : "";
      if (confirm(`Cancel booking for seat ${seat.label}${who}? This frees the seat and cannot be undone.`)) {
        await fetch(`/admin/api/bookings/${seat.booking_id}/cancel`, { method: "POST", headers: headers() });
        await loadSeats();
      }
      return;
    }
    if (selected.has(seat.id)) selected.delete(seat.id);
    else selected.add(seat.id);
    render();
  }

  async function loadSeats() {
    const res = await fetch("/admin/api/seats");
    const data = await res.json();
    seats = data.seats;
    render();
  }

  document.getElementById("btn-disable").addEventListener("click", async () => {
    if (!selected.size) return;
    await fetch("/admin/api/seats/disable", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ seat_ids: [...selected] }),
    });
    selected.clear();
    await loadSeats();
  });

  document.getElementById("btn-enable").addEventListener("click", async () => {
    if (!selected.size) return;
    await fetch("/admin/api/seats/enable", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ seat_ids: [...selected] }),
    });
    selected.clear();
    await loadSeats();
  });

  const panel = document.getElementById("admin-panel");
  document.getElementById("btn-book-cash").addEventListener("click", () => {
    if (!selected.size) { alert("Select one or more seats first."); return; }
    panel.classList.add("open");
  });
  document.getElementById("cash-cancel").addEventListener("click", () => panel.classList.remove("open"));

  document.getElementById("cash-submit").addEventListener("click", async () => {
    const name = document.getElementById("cash-name").value.trim();
    const email = document.getElementById("cash-email").value.trim();
    const phone = document.getElementById("cash-phone").value.trim();
    const notes = document.getElementById("cash-notes").value.trim();
    if (!name || !email) { alert("Name and email are required."); return; }

    const res = await fetch("/admin/api/bookings/cash", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ seat_ids: [...selected], name, email, phone, notes }),
    });
    const data = await res.json();
    if (data.ok) {
      alert(`Booking ${data.reference} created.`);
      selected.clear();
      panel.classList.remove("open");
      document.getElementById("cash-name").value = "";
      document.getElementById("cash-email").value = "";
      document.getElementById("cash-phone").value = "";
      document.getElementById("cash-notes").value = "";
      location.reload();
    } else {
      alert(data.error || "Could not create booking.");
      await loadSeats();
    }
  });

  document.querySelectorAll(".cancel-booking").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Cancel this booking and free its seats?")) return;
      await fetch(`/admin/api/bookings/${btn.dataset.id}/cancel`, { method: "POST", headers: headers() });
      location.reload();
    });
  });

  loadSeats();
  setInterval(loadSeats, 6000);
})();
