(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setupCarousel(containerId, options) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const track = el.querySelector(".sponsor-carousel-track");
    if (!track) return;

    const speed = options.speed || 0.4; // px per frame
    const direction = options.direction === "reverse" ? -1 : 1;

    // el.scrollLeft rounds to a whole pixel on every write, so accumulating
    // a sub-1px-per-frame speed directly on it never moves at all (each
    // fractional remainder gets thrown away before the next frame adds to
    // it). Track the true position as a float here instead, and only ever
    // write the rounded value out to the element.
    let position = 0;
    let dragging = false;
    let autoPaused = false;
    let pointerId = null;
    let startX = 0;
    let startPosition = 0;
    let resumeTimer = null;

    // The track is rendered twice back-to-back, so wrapping at the halfway
    // point is seamless - the second copy is pixel-identical to the first.
    function halfWidth() {
      return track.scrollWidth / 2;
    }

    function wrap() {
      const half = halfWidth();
      if (half <= 0) return;
      if (position >= half) position -= half;
      else if (position < 0) position += half;
    }

    function apply() {
      el.scrollLeft = Math.round(position);
    }

    // Reverse-direction rows need room to move left before hitting 0, so
    // start them partway through the (duplicated) track. Deferred to the
    // next frame since track.scrollWidth is 0 until images finish loading.
    function initPosition() {
      position = direction < 0 ? halfWidth() : 0;
      apply();
    }
    requestAnimationFrame(initPosition);

    function tick() {
      if (!autoPaused && !dragging && !reduceMotion) {
        position += speed * direction;
        wrap();
        apply();
      }
      requestAnimationFrame(tick);
    }

    function pauseThenResumeSoon() {
      autoPaused = true;
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => { autoPaused = false; }, 1200);
    }

    el.addEventListener("mouseenter", () => { autoPaused = true; });
    el.addEventListener("mouseleave", () => { if (!dragging) autoPaused = false; });

    el.addEventListener("pointerdown", (e) => {
      dragging = true;
      pointerId = e.pointerId;
      startX = e.clientX;
      startPosition = position;
      el.classList.add("dragging");
      clearTimeout(resumeTimer);
    });

    el.addEventListener("pointermove", (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      position = startPosition - (e.clientX - startX);
      wrap();
      apply();
    });

    function endDrag(e) {
      if (!dragging || (pointerId !== null && e.pointerId !== pointerId)) return;
      dragging = false;
      pointerId = null;
      el.classList.remove("dragging");
      pauseThenResumeSoon();
    }
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);

    requestAnimationFrame(tick);
  }

  // "forward" (increasing position) reads visually as right-to-left, and
  // "reverse" as left-to-right - the requested main (left->right) and gold
  // (right->left) directions are therefore the reverse/forward pairing.
  setupCarousel("sponsor-carousel-main", { speed: 0.35, direction: "reverse" });
  setupCarousel("sponsor-carousel-gold", { speed: 0.35, direction: "forward" });
})();
