# Session Log

## 2026-07-31 (cont.) — Crop-end loop fix, mrt 2.0.3, captioned demo video

**Files changed:**
- `loop_lab.py` — **fix:** a crop region whose right edge sits at the very end of the clip now loops. Root cause: with a region set, playback runs `loop=false` and `timeupdate` never fires `currentTime >= end` at the exact end, so it played once and stopped; added an `ended` handler that restarts from the region start. Committed `e3cb9fd`.
- `README.md` — demo link now points to the **captioned** YouTube video (`p-8k2D1gDCQ`), starting at 0:00. Committed `4636348`.
- `docs/loop-lab-demo-captioned.mp4` — **not committed** (`*.mp4` is gitignored by repo convention; the demo lives on YouTube). Built by overlaying 6 brand-styled caption PNGs (rendered via headless Chrome, transparent bg) onto the demo with `ffmpeg`. This `ffmpeg` has **no `drawtext`/`subtitles`/libass**, so the PNG-overlay + `ffmpeg overlay`/`fade` route is the caption path here (ScreenKite was avoided — prior difficulties).

**Env / external (not repo):**
- Upgraded `magenta-rt` **2.0.2 → 2.0.3** in the mrt venv via `uv` (venv has no pip). Verified the `mrt` CLI loads and every flag Loop Lab calls (`--prompt/--model/--duration/--temperature/--top-k/--cfg-musiccoca`) is present.
- Shared Loop Lab in the Magenta RealTime GitHub Discussions (Show and tell).
- Uploaded the captioned demo to YouTube (https://youtu.be/p-8k2D1gDCQ) with chapters + description.

**Still to do:**
- `docs/index.html` pre-session uncommitted edit still left alone.

## 2026-07-31 — Region crop-loop, guide panel, delete-selected, UI polish; docs + push

**Files changed:**
- `loop_lab.py` — waveform **region select** (drag) + loop-just-that-region playback; **crop-on-save** via stdlib `wave` (region-aware `/api/keep`, sample-accurate; crop lands under a `_<start>-<end>s.wav` name); **`Delete selected`** button (bins to Trash); collapsible **`guide`** panel; colour/legibility pass (brighter `--dim` grey `#8b9097`→`#a5aab2`, brighter prompt text `#f7f6f3`, yellow placeholder + model text, white "Generate", bigger pink guide triangle, yellow bold "Saved" status, "slide a fader" copy). A `CHARACTER` fader (CFG+top-k combined) was tried then **reverted to `Complexity`** — CFG (`--cfg-musiccoca`) only amplifies prompt adherence, it does **not** remove MRT's mumbled vocal artefacts (model limitation, no fader fixes it). Committed `cc2077b`.
- `README.md` — documented region loop, crop-on-save, guide, and the loop-gap caveat. Committed `57f9858`.
- `docs/screenshot.png` — refreshed hero screenshot to the new UI (headless-Chrome capture, needed a long `--virtual-time-budget` for the Web-Audio waveforms to render). Committed `57f9858`.
- `docs/crop-region.png` — added; user-supplied shot showing a selected region. Committed `93c2859`.

**Git:** local `main` had diverged from GitHub (7 unpushed commits locally vs 2 browser-made README edits on github.com). Reconciled with `push --force-with-lease` (local is source of truth; the 2 remote edits were a trivial demo-section re-indent), then normal pushes. `main` now in sync with `origin/main`.

**Still to do:**
- `docs/index.html` has an unrelated pre-session uncommitted edit — left alone this session.
- Possible niceties: draggable region edge handles; show region length in the clip meta line.

## 2026-06-11 — README demo video + GitHub embed
- Compressed `docs/Loop Lab - final.mp4` (13 MB) → **`docs/loop-lab-demo.mp4`** (4.6 MB, 1280×720, CRF 28, faststart) so it fits GitHub's video attachment limit (~10 MB; the 13 MB original was silently rejected when dragged into the README editor).
- Added a **Demo** section to `README.md` with a `REPLACE_ME` placeholder URL and a kept screenshot fallback (commit `6b3ca23`).
- **To finish (user, on github.com):** push, then drag `docs/loop-lab-demo.mp4` onto the placeholder line in GitHub's README editor so it becomes a `github.com/user-attachments/assets/…` URL; commit only after the real URL replaces `REPLACE_ME`.
- `loop-lab-demo.mp4` left untracked on purpose — the embed hosts it on GitHub's CDN, no need to bloat the repo.

## 2026-06-11 — Project initiated + promo video cards
- Project structure scaffolded (CLAUDE.md, SESSION_LOG.md, memory palace; git already existed on `main`).
- Built two animated promo cards for the demo screen recording (`docs/Loop Lab Recording.skbundle`):
  - **Title card** — recreates the Loop Lab UI, types the two demo prompts ("Liquid 909" → "Gangster Rap") with each prompt's real fader settings, Generate pulse.
  - **End card** — LOOP LAB logo + `github.com/mgoldhack/loop-lab` + "★ Star it on GitHub".
  - Sources (HyperFrames HTML/GSAP): `~/ScreenKiteWorkspace/loop-lab-cards/{title,endcard}/`.
- Delivered **`docs/Loop Lab - final.mp4`** (150.7s, 1330×748): title → recording → end card, audio baked in.
- **ScreenKite limitation found:** it composites a *prepended* full-screen card (title is live in the .skbundle project) but **cannot** composite a *trailing* full-screen card — a held last-frame covers any post-roll overlay. End card was therefore appended via ffmpeg in the final render, not in the ScreenKite project.
- ScreenKite MCP HTTP server (v1.8.1) is buggy (rejects reused sessions); use the `screenkite agent ...` CLI instead.
- **Loose ends / follow-ups:**
  - Final video is at the project's native **1330×748** (the recording's canvas size), not 1080p. Bumping would need canvas/upscale work.
  - A harmless screen-clip **split** remains in the `.skbundle` from testing (two contiguous pieces, plays seamlessly) — can `undo`/ignore.
  - No audio fades at the card seams (title & end card are silent; music hard-starts/stops). Add short fades if desired.
  - End card lives only in `Loop Lab - final.mp4`; re-export from ScreenKite gives title + recording only, then re-run the ffmpeg append.
