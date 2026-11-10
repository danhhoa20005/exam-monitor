// FT-11 audio alert: two short beeps from the Web Audio API (no sound file to ship).
// Browsers only allow audio after a user gesture; starting the camera / picking a video counts,
// and the mute toggle calls unlockAlertSound() so a click there unlocks it too.

let ctx: AudioContext | null = null;
let lastBeepMs = 0;
const MIN_GAP_MS = 1500;   // several students flagged in the same second -> one alert, not a burst

function context(): AudioContext | null {
  if (!ctx) {
    const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
  }
  if (ctx.state === 'suspended') void ctx.resume();
  return ctx;
}

export function unlockAlertSound() {
  context();
}

export function playAlertBeep() {
  const now = Date.now();
  if (now - lastBeepMs < MIN_GAP_MS) return;
  lastBeepMs = now;
  const ac = context();
  if (!ac) return;
  [0, 0.22].forEach(offset => {
    const t = ac.currentTime + offset;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = 'sine';
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    osc.connect(gain).connect(ac.destination);
    osc.start(t);
    osc.stop(t + 0.18);
  });
}
