(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Countdown -----------------------------------------------------
  const target = new Date(window.EVENT_DATETIME_ISO).getTime();
  const elDays = document.getElementById("cd-days");
  const elHours = document.getElementById("cd-hours");
  const elMins = document.getElementById("cd-mins");
  const elSecs = document.getElementById("cd-secs");

  function pad(n) { return String(n).padStart(2, "0"); }

  function tickCountdown() {
    const diff = target - Date.now();
    if (diff <= 0) {
      elDays.textContent = elHours.textContent = elMins.textContent = elSecs.textContent = "00";
      return;
    }
    const s = Math.floor(diff / 1000);
    elDays.textContent = pad(Math.floor(s / 86400));
    elHours.textContent = pad(Math.floor((s % 86400) / 3600));
    elMins.textContent = pad(Math.floor((s % 3600) / 60));
    elSecs.textContent = pad(s % 60);
  }
  if (elDays) {
    tickCountdown();
    setInterval(tickCountdown, 1000);
  }

  // ---- Live seats-remaining badge -------------------------------------
  const badge = document.getElementById("seats-remaining-badge");
  const countEl = document.getElementById("seats-remaining-count");

  async function refreshSeatsRemaining() {
    try {
      const res = await fetch("/api/seats");
      const data = await res.json();
      const available = data.seats.filter((s) => s.status === "available").length;
      countEl.textContent = available;
      badge.classList.toggle("urgent", available > 0 && available <= 40);
    } catch (e) {
      // leave previous value showing
    }
  }
  if (badge) {
    refreshSeatsRemaining();
    setInterval(refreshSeatsRemaining, 15000);
  }

  // ---- Ambient fireworks canvas ----------------------------------------
  const canvas = document.getElementById("fireworks-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let particles = [];
  let width, height, dpr;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  const COLORS = ["#ff3b3b", "#ffb347", "#ffffff", "#ffd54b"];

  function burst() {
    const x = width * (0.15 + Math.random() * 0.7);
    const y = height * (0.15 + Math.random() * 0.45);
    const count = 26 + Math.floor(Math.random() * 14);
    const color = COLORS[Math.floor(Math.random() * COLORS.length)];
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.2;
      const speed = 1.2 + Math.random() * 2.2;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1,
        decay: 0.012 + Math.random() * 0.012,
        color,
      });
    }
  }

  function frame() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.02; // gravity
      p.life -= p.decay;
      if (p.life > 0) {
        ctx.globalAlpha = Math.max(p.life, 0);
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    ctx.globalAlpha = 1;
    particles = particles.filter((p) => p.life > 0);
    requestAnimationFrame(frame);
  }

  if (!reduceMotion) {
    requestAnimationFrame(frame);
    burst();
    setInterval(burst, 2400);
  }

  // ---- Programme cards: reveal as they scroll into view ----------------
  const cards = document.querySelectorAll(".programme-card");
  if (cards.length && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    cards.forEach((card) => observer.observe(card));
  } else {
    cards.forEach((card) => card.classList.add("in-view"));
  }

  // ---- Marketing funnel: log the "Book Your Seat" CTA click ------------
  const bookCta = document.getElementById("book-cta");
  if (bookCta) {
    bookCta.addEventListener("click", () => {
      fetch("/api/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: "book_cta_click" }),
      }).catch(() => {});
    });
  }
})();
