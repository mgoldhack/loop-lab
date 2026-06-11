---
name: github-readme-video
description: How to embed a playable video in a GitHub README, and the silent ~10MB upload limit
metadata:
  type: reference
---

GitHub won't play a video from a committed file path or raw URL. To embed a player in a README/issue/PR:

1. In GitHub's web editor (or a new issue as scratchpad), **drag the video file into the text area**. GitHub uploads it to its CDN and inserts a `https://github.com/user-attachments/assets/<uuid>` URL.
2. Put that URL **on its own line** — it renders as an inline player. Keeps the binary off the repo (CDN-hosted).

**Gotcha:** the upload limit is small (~10 MB on Free accounts) and oversized files are **silently rejected** — no error, the paste just does nothing. Compress first. For Loop Lab the 13 MB final was rejected; a 4.6 MB version worked:

```bash
ffmpeg -i in.mp4 -vf scale=1280:-2 -c:v libx264 -crf 28 -preset slow \
  -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart out.mp4
```

For larger/HQ clips, attach as a **GitHub Release asset** (100 MB+) and link, or use Git LFS for a Pages-hosted `<video>` tag.
