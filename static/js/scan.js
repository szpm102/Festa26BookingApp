(function () {
  const video = document.getElementById("scan-video");
  const canvas = document.getElementById("scan-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const msgEl = document.getElementById("scan-msg");
  const switchBtn = document.getElementById("scan-switch-camera");

  let stream = null;
  let scanning = true;
  let facingMode = "environment";
  let cameras = [];

  function flash(message, type) {
    msgEl.innerHTML = `<div class="msg ${type}">${message}</div>`;
  }

  function stopStream() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
  }

  async function startCamera() {
    stopStream();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      requestAnimationFrame(tick);
    } catch (err) {
      flash(
        "Could not access the camera: " + err.message +
        ". Make sure you allowed camera access, and that this page is loaded over HTTPS.",
        "error"
      );
    }
  }

  function looksLikeCheckinLink(text) {
    try {
      const url = new URL(text, window.location.origin);
      return url.pathname.includes("/admin/checkin/");
    } catch (e) {
      return false;
    }
  }

  function tick() {
    if (!scanning) return;
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: "dontInvert",
      });
      if (code && code.data) {
        if (looksLikeCheckinLink(code.data)) {
          scanning = false;
          flash("Ticket recognised - opening...", "success");
          stopStream();
          window.location.href = code.data;
          return;
        }
        flash("That QR code doesn't look like a festa ticket. Keep scanning.", "error");
      }
    }
    requestAnimationFrame(tick);
  }

  navigator.mediaDevices.enumerateDevices().then((devices) => {
    cameras = devices.filter((d) => d.kind === "videoinput");
    if (cameras.length > 1) {
      switchBtn.style.display = "inline-block";
    }
  }).catch(() => {});

  switchBtn.addEventListener("click", () => {
    facingMode = facingMode === "environment" ? "user" : "environment";
    startCamera();
  });

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    flash("Camera access isn't supported in this browser. Use the dashboard's manual lookup instead.", "error");
  } else {
    startCamera();
  }

  window.addEventListener("beforeunload", stopStream);
})();
