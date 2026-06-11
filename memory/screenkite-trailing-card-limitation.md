---
name: screenkite-trailing-card-limitation
description: ScreenKite composites a prepended full-screen card but NOT a trailing one — append via ffmpeg
metadata:
  type: reference
---

In a ScreenKite recording project, `editTimeline insertMedia` puts media on an overlay track and creates a real gap on the main recording track.

- **Prepend (insert at t=0): works.** The leading gap has no prior frame, so the full-screen card composites over black. Verified live in the export.
- **Append / trailing (insert at or past the recording's end): does NOT render.** ScreenKite holds the recording's last frame across any post-roll/gap and composites it *over* the overlay, so the trailing card is invisible — even though the clip is correctly placed and the overlay track is above the screen track. A mid-gap (split + insert) fails the same way (the prior clip's last frame is held forward).

**Workaround:** keep the title card in the ScreenKite project (prepend works), then build the final video outside ScreenKite: `exportArtifact type=project_video` → ffmpeg-concat the end card after it (scale to the project canvas, add silent audio for the card segment, re-encode h264/aac). See [[loop-lab-promo-cards]].

**Verify renders with the real pipeline** (`exportArtifact type=range`), not `peekFrame` (fails on gap regions) or `vfxExportVideoSegment` (freezes the last screen frame in post-roll — gave false "wallpaper" frames).
