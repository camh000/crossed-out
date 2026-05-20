#!/usr/bin/env python3
"""Post-build hook that decorates pygbag's generated `build/web/index.html`
with a branded loading overlay.

The default pygbag boot shows a black canvas + a small status banner while
the Python interpreter + WebAssembly bundle download (~3-5 seconds on a
phone). This script slips a CSS-animated 'CROSSED OUT' splash overlay on
top of that, with the same gold/navy palette the game uses, then hides
it once the game's canvas starts drawing.

Designed to be idempotent — running it twice is a no-op (a sentinel
comment is checked before re-injecting)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SENTINEL = "<!-- crossed-out:loader-injected -->"


CSS = """\
/* Crossed Out loading overlay — fades out once pygame begins drawing. */
#cx-loader {
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse at center, #14142a 0%, #07070f 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  font-family: ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace;
  color: #f0c040;
  transition: opacity 600ms ease-out;
  user-select: none;
  -webkit-user-select: none;
}
#cx-loader.cx-hidden { opacity: 0; pointer-events: none; }
#cx-loader h1 {
  font-size: clamp(36px, 8vw, 64px);
  margin: 0 0 6px 0;
  letter-spacing: 0.18em;
  font-weight: 900;
  text-shadow: 0 0 28px rgba(240, 192, 64, 0.45);
}
#cx-loader .cx-sub {
  color: #a0a0c0;
  font-size: clamp(12px, 3vw, 16px);
  letter-spacing: 0.24em;
  text-transform: uppercase;
  margin-bottom: 36px;
}
#cx-loader .cx-row {
  display: flex;
  gap: 18px;
  margin-bottom: 28px;
}
#cx-loader .cx-mark {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  color: #64b4ff;
  font-weight: 700;
  font-size: 28px;
  background: rgba(28, 28, 48, 0.7);
  border-radius: 6px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), inset 0 -1px 0 rgba(0,0,0,0.4);
  animation: cx-pop 1.4s ease-out infinite;
}
#cx-loader .cx-mark:nth-child(2) { animation-delay: 0.18s; color: #ff6464; }
#cx-loader .cx-mark:nth-child(3) { animation-delay: 0.36s; color: #64b4ff; }
#cx-loader .cx-mark:nth-child(4) { animation-delay: 0.54s; color: #ff6464; }
@keyframes cx-pop {
  0%, 60%, 100% { transform: scale(1.0); opacity: 0.5; }
  20% { transform: scale(1.15); opacity: 1.0; }
}
#cx-loader .cx-status {
  color: #707088;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
#cx-loader .cx-bar {
  width: min(280px, 60vw);
  height: 4px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 16px;
}
#cx-loader .cx-bar > div {
  height: 100%;
  width: 36%;
  background: linear-gradient(90deg, transparent, #f0c040, transparent);
  animation: cx-slide 1.6s ease-in-out infinite;
}
@keyframes cx-slide {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(380%); }
}
@media (prefers-reduced-motion: reduce) {
  #cx-loader .cx-mark, #cx-loader .cx-bar > div { animation: none; }
}
"""


OVERLAY = """\
<div id="cx-loader" role="status" aria-live="polite">
  <h1>CROSSED OUT</h1>
  <div class="cx-sub">A roguelite tic-tac-toe</div>
  <div class="cx-row">
    <div class="cx-mark">X</div>
    <div class="cx-mark">O</div>
    <div class="cx-mark">X</div>
    <div class="cx-mark">O</div>
  </div>
  <div class="cx-status">Loading runtime...</div>
  <div class="cx-bar"><div></div></div>
</div>
"""


# Watches for either the pygame canvas to actually render something, or for
# a long enough fallback timeout, then fades the overlay out. We can't rely
# on a specific pygbag event because the runtime version may change; the
# "canvas painted a non-empty frame" heuristic works across versions.
SCRIPT = """\
<script>
(function () {
  var loader = document.getElementById('cx-loader');
  if (!loader) return;
  var hidden = false;
  function hide() {
    if (hidden) return;
    hidden = true;
    loader.classList.add('cx-hidden');
    setTimeout(function () {
      if (loader.parentNode) loader.parentNode.removeChild(loader);
    }, 700);
  }
  function canvasHasPaint() {
    // Pygbag creates a <canvas>. Wait until it's sized AND has at least one
    // non-zero pixel — that's the first frame pygame drew.
    var c = document.querySelector('canvas');
    if (!c || c.width === 0 || c.height === 0) return false;
    try {
      var ctx = c.getContext('webgl2') || c.getContext('webgl') || c.getContext('2d');
      // We can't read pixels from a WebGL canvas without preserveDrawingBuffer.
      // Fall back to "canvas has non-zero CSS size and existed for >300ms".
      if (!ctx || !ctx.getImageData) {
        return c.getBoundingClientRect().width > 0;
      }
      // Sample a tiny strip from the centre of the canvas.
      var data = ctx.getImageData(c.width >> 1, c.height >> 1, 1, 1).data;
      return data[0] + data[1] + data[2] > 0;
    } catch (e) {
      return c.getBoundingClientRect().width > 0;
    }
  }
  var start = Date.now();
  function tick() {
    if (canvasHasPaint()) { hide(); return; }
    // Safety net: hide after 30s no matter what so the player isn't stuck
    // behind the overlay if the readiness probe fails.
    if (Date.now() - start > 30000) { hide(); return; }
    requestAnimationFrame(tick);
  }
  // Defer one frame so pygbag has a chance to insert its canvas first.
  requestAnimationFrame(function () { requestAnimationFrame(tick); });
})();
</script>
"""


def inject(index_path: Path) -> bool:
    text = index_path.read_text(encoding="utf-8")
    if SENTINEL in text:
        print(f"loader already injected in {index_path}", file=sys.stderr)
        return False

    # Insert CSS just before </head> (case-insensitive) and overlay +
    # script just before </body>.
    style_block = f"\n{SENTINEL}\n<style>\n{CSS}</style>\n"
    body_block = f"\n{OVERLAY}\n{SCRIPT}\n"

    head_close = re.compile(r"</head\s*>", re.IGNORECASE)
    body_close = re.compile(r"</body\s*>", re.IGNORECASE)

    if not head_close.search(text):
        print("WARNING: no </head> tag found; inserting at top of file", file=sys.stderr)
        text = style_block + text
    else:
        text = head_close.sub(style_block + "</head>", text, count=1)

    if not body_close.search(text):
        print("WARNING: no </body> tag found; appending overlay at end", file=sys.stderr)
        text = text + body_block
    else:
        text = body_close.sub(body_block + "</body>", text, count=1)

    index_path.write_text(text, encoding="utf-8")
    print(f"injected loader into {index_path}")
    return True


def main() -> int:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path("build/web/index.html")
    if not target.is_file():
        print(f"ERROR: {target} not found. Run the pygbag build first.", file=sys.stderr)
        return 1
    inject(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
