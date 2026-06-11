---
name: screenkite-use-cli
description: Drive ScreenKite via the `screenkite agent` CLI, not its MCP HTTP server (v1.8.1 is broken)
metadata:
  type: reference
---

ScreenKite exposes a window-bound MCP HTTP server (e.g. `http://127.0.0.1:56300/mcp`), but **v1.8.1's session handling is broken**: it issues an `Mcp-Session-Id` on `initialize` then rejects that same id on the next request ("Session not initialized"). So Claude Code's MCP client always shows ✘ Failed to connect, and that `screenkite-video-editor` MCP entry was removed.

**Use the CLI instead** — it's installed at `/usr/local/bin/screenkite` and handles sessions internally:
- `screenkite agent project open --path '<bundle>.skbundle' --json`
- `screenkite agent tool list --json` / `tool describe --name <T>` / `tool call --name <T> --input-json '{...}' --json`
- Key tools: `getProjectState` (scopes: summary/layout/full/visual/transitions), `peekFrame` (needs a `path`), `editTimeline` (insertMedia/split/cut/transition/move/delete), `manageHyperFrames`, `setSceneLayout`, `exportArtifact` (project_video/range/...), `vfxExportVideoSegment`.

Some notification-emitting calls (e.g. `getTranscriptionReadiness`) still hit the v1.8.1 bug ("Notification rejected, HTTP 400"); read/edit tools work fine. See [[screenkite-trailing-card-limitation]].
