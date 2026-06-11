# Session Log

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
