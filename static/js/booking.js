(function () {
  const mapEl = document.getElementById("seat-map");
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

  function render() {
    const byRow = {};
    seats.forEach((s) => {
      byRow[s.row] = byRow[s.row] || [];
      byRow[s.row].push(s);
    });

    const rows = Object.keys(byRow).sort();
    mapEl.innerHTML = "";
    rows.forEach((row) => {
      const rowDiv = document.createElement("div");
      rowDiv.className = "seat-row";
      const label = document.createElement("div");
      label.className = "row-label";
      label.textContent = row;
      rowDiv.appendChild(label);

      byRow[row]
        .sort((a, b) => a.number - b.number)
        .forEach((seat) => {
          const btn = document.createElement("button");
          btn.className = `seat status-${seat.status}`;
          btn.textContent = seat.number;
          btn.title = `Seat ${seat.label}`;
          btn.disabled = ["held", "booked", "disabled"].includes(seat.status);
          btn.addEventListener("click", () => onSeatClick(seat));
          rowDiv.appendChild(btn);
        });

      mapEl.appendChild(rowDiv);
    });

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
