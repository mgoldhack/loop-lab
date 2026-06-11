# Loop Lab

A small local web interface for generating and curating short audio loops with
[Magenta RealTime 2](https://github.com/magenta/magenta-realtime) on Apple
Silicon. Type a prompt, pull a few faders, get a batch of variations you can
audition, save the good ones, and bin the rest — without touching the command
line each time.

> **Unofficial.** This is a third-party front-end. It runs Google's `mrt`
> command under the hood; it does not include or modify Magenta itself. You
> install magenta-rt separately (see below). Not affiliated with Google.

![A prompt box, four faders (outputs, length, randomness, complexity), and a
list of generated loops with waveforms.](docs/screenshot.png)

## What it does

- **Prompt → a batch of loops.** One text prompt generates several clips at
  once, each at a slightly different temperature so they actually differ
  (the model uses a fixed seed, so identical settings would otherwise produce
  identical audio).
- **Four faders, real units.** Outputs (clip count), Length (seconds),
  Randomness (sampling temperature), Complexity (top-k).
- **Audition in the browser.** Looping playback with a waveform and playhead.
- **Curate.** Tick the keepers and save them to a folder; delete the rest to
  the macOS Trash.
- **Matched levels.** Every clip is loudness-normalised on generation, so
  drums and synths come out at a consistent volume.

## Requirements

- An **Apple Silicon Mac** (M1 or later). Magenta RealTime's MLX backend does
  not run on Intel.
- **Python 3.12**.
- **[magenta-rt](https://github.com/magenta/magenta-realtime) installed**, with
  its models downloaded (steps below).

## Setup

### 1. Install magenta-rt and its models

Loop Lab does not bundle Magenta — install it first, following the
[official instructions](https://github.com/magenta/magenta-realtime). In short:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install "magenta-rt[mlx]"
mrt models init           # helper models (MusicCoCa, SpectroStream)
mrt models download       # choose mrt2_small (real-time) and/or mrt2_base
```

Confirm it works on its own before going further:

```bash
mrt mlx generate --prompt "techno drum loop" --duration 4.0 --model=mrt2_small
```

### 2. Install Loop Lab's dependencies

In the **same activated environment** (so `mrt` is on PATH):

```bash
pip install -r requirements.txt
```

(If you used `uv` for the venv, use `uv pip install -r requirements.txt`.)

### 3. Run it

```bash
python loop_lab.py
```

Open <http://localhost:8765>. Leave the terminal running — it's the server.
`Ctrl+C` stops it.

## Configuration

All optional, set as environment variables:

| Variable                | Default                                  | Purpose                                  |
| ----------------------- | ---------------------------------------- | ---------------------------------------- |
| `LOOP_LAB_MAGENTA_HOME` | `~/Documents/Magenta/magenta-rt-v2`      | Your magenta-rt install (where models live) |
| `LOOP_LAB_KEEPERS`      | `~/Music/Loop Lab`                       | Where "Save selected" copies loops       |
| `LOOP_LAB_PORT`         | `8765`                                   | Server port                              |

Example — save keepers straight into a synced folder:

```bash
LOOP_LAB_KEEPERS="$HOME/Dropbox/Loops" python loop_lab.py
```

## How clips are stored

- Generated clips live in `<magenta-home>/outputs/loop-lab/`.
- **Save** copies selected clips to your keepers folder (the originals stay).
- **Delete (✕)** sends a clip to the macOS Trash — recoverable in Finder until
  you empty it.

## Notes & limitations

- macOS only (the Trash routing and the MLX backend are both Mac-specific).
- `mrt2_small` runs in real-time on any Apple Silicon; `mrt2_base` is higher
  quality but only runs offline on base chips — fine for batch loop rendering.
- The four faders are deliberately simple mappings onto the two sampling
  controls the CLI exposes (`--temperature`, `--top-k`) plus count and duration.
  Tweak the ranges in `map_settings()` if they don't suit your material.

## Licence

MIT — see [LICENSE](LICENSE). Magenta RealTime is Google's and is covered by
its own (Apache 2.0) licence; this project only calls its CLI.
