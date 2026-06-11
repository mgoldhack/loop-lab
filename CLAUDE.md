# Loop Lab

## Overview
A small local web interface for generating and curating short audio loops with
Magenta RealTime 2 (`mrt`) on Apple Silicon. Type a prompt, pull four faders
(Outputs / Length / Randomness / Complexity), generate a batch of variations,
audition them in-browser, keep the good ones, bin the rest. Unofficial
third-party front-end over Google's `mrt` CLI — does not bundle or modify
Magenta itself.

## Key files
- `loop_lab.py` — the entire app (local web server + generation logic)
- `README.md` — setup, requirements (Apple Silicon, Python 3.12, magenta-rt), usage
- `requirements.txt` — Python dependencies
- `docs/` — `screenshot.png` (UI reference), `Loop Lab Recording.skbundle` /
  `.mov` (demo screen recording), `Loop Lab - final.mp4` (recording with title +
  end cards), `loop-lab-demo.mp4` (4.6 MB web/README version); promo-card sources
  live in `~/ScreenKiteWorkspace/loop-lab-cards/`

## Critical rules
- **Unofficial / not affiliated with Google.** Keep that framing in any
  user-facing copy. Don't imply endorsement.
- Generated audio (`*.wav`), `outputs/`, and `manifest.json` are gitignored —
  they are artifacts, not source. Don't commit them.
- Brand: dark UI, magenta accent `#EC1E8C`, bold "LOOP LAB" wordmark with the
  second "O" in magenta, mono labels. GitHub: github.com/mgoldhack/loop-lab

## Workflow
- Run the app: see `README.md` (needs magenta-rt installed + models downloaded
  in a Python 3.12 venv; `mrt models download`).
- Loops are generated per-prompt at varied temperature so a batch actually
  differs (the model uses a fixed seed).
- Demo video editing is done in ScreenKite (see SESSION_LOG for the promo-card
  work and the trailing-overlay limitation).
