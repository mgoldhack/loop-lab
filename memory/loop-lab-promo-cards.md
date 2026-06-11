---
name: loop-lab-promo-cards
description: Where the Loop Lab title/end promo cards live and how to re-render + re-assemble the final video
metadata:
  type: project
---

Promo cards for the Loop Lab demo recording (`docs/Loop Lab Recording.skbundle`).

**Sources** (HyperFrames = HTML + GSAP, rendered via `npx hyperframes render`):
- `~/ScreenKiteWorkspace/loop-lab-cards/title/index.html` — recreates the Loop Lab UI; types the two demo prompts **"Liquid 909"** (4·8·1.05·130) → **"Gangster Rap"** (2·12·0.9·190) with Generate pulse. ~7s.
- `~/ScreenKiteWorkspace/loop-lab-cards/endcard/index.html` — LOOP LAB logo + `github.com/mgoldhack/loop-lab` + "★ Star it on GitHub". ~5s.
- Both 1920×1080@30. Brand: bg `#0E0E13`, magenta `#EC1E8C`, mono labels, wordmark with 2nd "O" magenta. System fonts (`-apple-system`/Menlo) render correctly on this Mac.

**Deliverable:** `docs/Loop Lab - final.mp4` (1330×748, 30fps) = title → recording → end card.

**Re-assemble** (after editing/re-rendering a card):
1. Re-render: `cd ~/ScreenKiteWorkspace/loop-lab-cards/<card> && npx hyperframes render . -o renders/<card>.mp4 -q high`
2. Title is prepended in the `.skbundle` (re-render only if changing it); export the project: `screenkite agent tool call --name exportArtifact --input-json '{"type":"project_video","path":"...mov"}' --json`
3. ffmpeg concat the end card after the export (scale 1330×748, add `anullsrc` silent audio for the 5s, concat filter → h264/aac). The exact command is in the session transcript.

**Title card audio:** HyperFrames renders are silent, so the title's loop sounds are added at the ffmpeg stage. Snippets are extracted from the recording's `system_audio_0.m4a` (no mic → pure loop audio): Liquid 909 loops play ~33–68s, Gangster Rap ~108–129s in that file. A 7s bed (Liquid @1.1s, Gangster @3.4s, matching the typing) is `amix`ed onto the final's first 7s. Snippets/bed live in `~/ScreenKiteWorkspace/loop-lab-cards/audio/`.

The end card can't live in the ScreenKite project — see [[screenkite-trailing-card-limitation]]. Drive ScreenKite via [[screenkite-use-cli]].
