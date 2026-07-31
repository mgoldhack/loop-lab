#!/usr/bin/env python3
"""
Loop Lab — a local web interface for Magenta RealTime 2 (MLX) loop generation.

An unofficial front-end for Google's Magenta RealTime. It shells out to the
`mrt mlx generate` command, so you must have magenta-rt installed and its
models downloaded first (see the README). Apple Silicon Mac required.

Quick start:
    source /path/to/your/magenta-venv/bin/activate
    pip install -r requirements.txt
    python loop_lab.py
Then open http://localhost:8765 in your browser.

Paths are configurable via environment variables (all optional):
    LOOP_LAB_MAGENTA_HOME   magenta-rt-v2 dir   (default ~/Documents/Magenta/magenta-rt-v2)
    LOOP_LAB_KEEPERS        where saved loops go (default ~/Music/Loop Lab)
    LOOP_LAB_PORT           server port          (default 8765)
"""

import json
import math
import os
import random
import re
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    import numpy as np
    import soundfile as sf
    _AUDIO = True
except Exception:
    _AUDIO = False

# ---------------------------------------------------------------- paths

MAGENTA_DIR = Path(os.environ.get(
    "LOOP_LAB_MAGENTA_HOME",
    str(Path.home() / "Documents" / "Magenta" / "magenta-rt-v2")))
OUTPUTS_DIR = MAGENTA_DIR / "outputs"
LIBRARY_DIR = OUTPUTS_DIR / "loop-lab"
MANIFEST = LIBRARY_DIR / "manifest.json"
PORT = int(os.environ.get("LOOP_LAB_PORT", "8765"))

LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def trash_file(path):
    """Send a file to the macOS Trash (recoverable in Finder until emptied).
    Falls back to permanent removal only if the Trash is somehow unwritable."""
    trash = Path.home() / ".Trash"
    try:
        dest = trash / path.name
        n = 1
        while dest.exists():
            dest = trash / f"{path.stem}_{n}{path.suffix}"
            n += 1
        shutil.move(str(path), str(dest))
    except Exception:
        try:
            path.unlink()
        except Exception:
            pass


def find_keepers_dir():
    """Where saved favourites go. Override with LOOP_LAB_KEEPERS; otherwise a
    local folder under ~/Music (point it at a cloud-synced folder if you like —
    these are a few small WAVs, not the gigabyte models)."""
    env = os.environ.get("LOOP_LAB_KEEPERS")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Music" / "Loop Lab"


def pretty_path(p):
    """Human-readable path for the UI (hides the ugly iCloud container name)."""
    s = str(p)
    icloud = str(Path.home() / "Library" / "Mobile Documents"
                 / "com~apple~CloudDocs")
    if s.startswith(icloud):
        return "iCloud Drive" + s[len(icloud):]
    return s.replace(str(Path.home()), "~")


KEEPERS_DIR = find_keepers_dir()
KEEPERS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ---------------------------------------------------------------- state

state_lock = threading.Lock()
status = {"busy": False, "done": 0, "total": 0, "message": "", "error": ""}


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            pass
    return {"clips": []}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, indent=2))


# ---------------------------------------------------------------- mapping
# All four UI controls are 1-10. These map them onto the real mrt flags.

def map_settings(data):
    """Faders now send real units directly: clips, seconds, temperature, top-k."""
    outputs = max(1, min(10, int(data.get("outputs", 4))))
    duration = max(1.0, min(30.0, float(data.get("duration", 8))))
    base_temp = max(0.60, min(1.60, float(data.get("temperature", 1.05))))
    top_k = max(10, min(300, int(data.get("top_k", 130))))
    return outputs, duration, base_temp, top_k


def spread_temps(base, n, avoid=None, around=None):
    """Produce n distinct temperatures around `base`.

    The model uses a fixed seed, so two runs with identical settings give
    identical audio: every clip MUST get its own temperature, or a batch
    comes out as N copies of the same loop."""
    avoid = avoid or []
    temps = []
    attempts = 0
    while len(temps) < n and attempts < 400:
        attempts += 1
        if around:
            centre = random.choice(around)
            t = centre + random.uniform(-0.06, 0.06)
        else:
            # symmetric spread around base, widening with n
            span = 0.05 + 0.02 * n
            t = base + random.uniform(-span, span)
        t = max(0.60, min(1.60, round(t, 2)))
        if any(abs(t - a) < 0.05 for a in avoid):
            continue
        if any(abs(t - x) < 0.02 for x in temps):
            continue
        temps.append(t)
    # fallback fill if constraints were too tight
    while len(temps) < n:
        temps.append(round(random.uniform(0.60, 1.60), 2))
    return temps


# ---------------------------------------------------------------- generation

def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s[:40] or "clip"


def normalize_file(path, target_rms_db=-18.0, peak_db=-1.0):
    """Match perceived loudness across clips: scale to a target RMS, then pull
    back if that would push the peak past the ceiling (prevents clipping).
    So drums and synths land at a consistent level, in-app and in Logic."""
    if not _AUDIO:
        return
    try:
        data, sr = sf.read(str(path))
        if data.size == 0:
            return
        rms = float(np.sqrt(np.mean(np.square(data)))) + 1e-9
        gain = (10 ** (target_rms_db / 20)) / rms
        peak = float(np.max(np.abs(data))) + 1e-9
        ceiling = 10 ** (peak_db / 20)
        if peak * gain > ceiling:
            gain = ceiling / peak
        sf.write(str(path), data * gain, sr)
    except Exception:
        pass


def run_generation(prompt, model, duration, top_k, temps):
    """Worker thread: run mrt once per temperature, harvest each file."""
    global status
    src = OUTPUTS_DIR / f"output_audio_mlx_{model}.wav"
    slug = slugify(prompt)
    manifest = load_manifest()

    for i, temp in enumerate(temps):
        with state_lock:
            status.update(done=i, total=len(temps),
                          message=f"Generating {i + 1}/{len(temps)} (temp {temp})")
        cmd = [
            "mrt", "mlx", "generate",
            "--prompt", prompt,
            "--model", model,
            "--duration", str(duration),
            "--temperature", str(temp),
            "--top-k", str(top_k),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=1800)
        except FileNotFoundError:
            with state_lock:
                status.update(busy=False, error="`mrt` not found — start Loop "
                              "Lab from a terminal with your venv activated.")
            return
        except subprocess.TimeoutExpired:
            with state_lock:
                status.update(busy=False, error="Generation timed out.")
            return

        if result.returncode != 0 or not src.exists():
            err = (result.stderr or result.stdout or "").strip()[-400:]
            with state_lock:
                status.update(busy=False,
                              error=f"mrt failed on clip {i + 1}: {err}")
            return

        name = f"{slug}_{int(time.time())}_{i + 1}_t{temp}.wav"
        shutil.move(str(src), str(LIBRARY_DIR / name))
        normalize_file(LIBRARY_DIR / name)
        manifest["clips"].append({
            "file": name, "prompt": prompt, "model": model,
            "duration": duration, "temp": temp, "top_k": top_k,
            "created": time.time(),
        })
        save_manifest(manifest)

    with state_lock:
        status.update(busy=False, done=len(temps),
                      message=f"Done — {len(temps)} clips ready", error="")


def start_worker(prompt, model, duration, top_k, temps):
    global status
    with state_lock:
        if status["busy"]:
            return False
        status.update(busy=True, done=0, total=len(temps),
                      message="Starting…", error="")
    t = threading.Thread(target=run_generation,
                         args=(prompt, model, duration, top_k, temps),
                         daemon=True)
    t.start()
    return True


# ---------------------------------------------------------------- API

@app.post("/api/generate")
def api_generate():
    data = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify(error="Type a prompt first."), 400
    model = data.get("model", "mrt2_small")
    outputs, duration, base_temp, top_k = map_settings(data)
    temps = spread_temps(base_temp, outputs)
    if not start_worker(prompt, model, duration, top_k, temps):
        return jsonify(error="Already generating — wait for the batch."), 409
    return jsonify(ok=True, temps=temps, duration=duration, top_k=top_k)


@app.get("/api/status")
def api_status():
    with state_lock:
        return jsonify(status)


@app.get("/api/clips")
def api_clips():
    m = load_manifest()
    clips = [c for c in m["clips"] if (LIBRARY_DIR / c["file"]).exists()]
    saved = {p.name for p in KEEPERS_DIR.glob("*.wav")}
    for c in clips:
        c["saved"] = c["file"] in saved
    clips.sort(key=lambda c: c["created"], reverse=True)
    return jsonify(clips=clips, keepers=pretty_path(KEEPERS_DIR))


def crop_wav(src, dst, start_frac, end_frac):
    """Write the [start_frac, end_frac] slice of a WAV to dst (sample-accurate)."""
    with wave.open(str(src), "rb") as w:
        n = w.getnframes()
        s = max(0, min(n, int(round(start_frac * n))))
        e = max(s, min(n, int(round(end_frac * n))))
        w.setpos(s)
        frames = w.readframes(e - s)
        with wave.open(str(dst), "wb") as out:
            out.setnchannels(w.getnchannels())
            out.setsampwidth(w.getsampwidth())
            out.setframerate(w.getframerate())
            out.writeframes(frames)


@app.post("/api/keep")
def api_keep():
    data = request.get_json(force=True)
    files = data.get("files", [])
    regions = data.get("regions") or {}
    saved = 0
    for name in files:
        if "/" in name or ".." in name:
            continue
        src = LIBRARY_DIR / name
        if not src.exists():
            continue
        reg = regions.get(name)
        if reg and float(reg.get("end", 0)) > float(reg.get("start", 0)):
            sf = max(0.0, float(reg["start"]))
            ef = min(1.0, float(reg["end"]))
            try:
                with wave.open(str(src), "rb") as w:
                    dur = w.getnframes() / float(w.getframerate())
                dst = KEEPERS_DIR / f"{src.stem}_{sf*dur:.1f}-{ef*dur:.1f}s{src.suffix}"
                crop_wav(src, dst, sf, ef)
                saved += 1
            except Exception:
                pass
        else:
            shutil.copy2(str(src), str(KEEPERS_DIR / name))
            saved += 1
    return jsonify(ok=True, saved=saved, dest=pretty_path(KEEPERS_DIR))


@app.delete("/api/clips/<name>")
def api_delete(name):
    if "/" in name or ".." in name:
        return jsonify(error="Bad name"), 400
    path = LIBRARY_DIR / name
    m = load_manifest()
    entry = next((c for c in m["clips"] if c["file"] == name), None)
    if path.exists():
        trash_file(path)
    if entry:
        m["clips"] = [c for c in m["clips"] if c["file"] != name]
        save_manifest(m)
    return jsonify(ok=True)


@app.get("/clips/<name>")
def serve_clip(name):
    return send_from_directory(LIBRARY_DIR, name)


# ---------------------------------------------------------------- UI

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loop Lab</title>
<style>
  :root{
    --bg:#15171c; --panel:#1d2027; --panel2:#23272f; --line:#2e333d;
    --text:#e9e7e1; --dim:#a5aab2; --mag:#d6418f; --mag-soft:#d6418f33;
    --amber:#d9a441; --red:#c25b4e;
    --mono:"SF Mono",ui-monospace,Menlo,monospace;
    --sans:-apple-system,"Helvetica Neue",Arial,sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       min-height:100vh;padding:28px 20px 80px}
  .wrap{max-width:860px;margin:0 auto}

  header{display:flex;align-items:baseline;gap:14px;margin-bottom:26px}
  h1{font-size:20px;letter-spacing:.14em;font-weight:700}
  h1 .o{color:var(--mag)}
  header .sub{font-family:var(--mono);font-size:11px;color:var(--dim)}

  .console{background:var(--panel);border:1px solid var(--line);
           border-radius:10px;padding:18px}
  .promptrow{display:flex;gap:10px}
  #prompt{flex:1;background:var(--panel2);border:1px solid var(--line);
          border-radius:8px;color:#f7f6f3;font:15px var(--sans);
          padding:12px 14px;outline:none}
  #prompt:focus{border-color:var(--mag)}
  #prompt::placeholder{color:var(--amber);opacity:.85}
  button{cursor:pointer;border:none;border-radius:8px;
         font:600 13px var(--sans);letter-spacing:.04em}
  #go{background:var(--mag);color:var(--text);padding:0 26px}
  #go:disabled{background:var(--line);color:var(--dim);cursor:default}

  /* fader bank */
  .bank{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;
        margin-top:18px}
  .fader{background:var(--panel2);border:1px solid var(--line);
         border-radius:8px;padding:12px 8px 10px;text-align:center}
  .fader label{display:block;font-family:var(--mono);font-size:10px;
         letter-spacing:.12em;color:var(--dim);margin-bottom:8px}
  .fader .val{font-family:var(--mono);font-size:14px;color:var(--mag);
         margin-top:8px}
  .fader .val em{font-style:normal;font-size:10px;letter-spacing:.1em;
         color:var(--dim)}
  input[type=range]{width:100%;accent-color:var(--mag)}

  .modeline{display:flex;justify-content:space-between;align-items:center;
            margin-top:14px;font-family:var(--mono);font-size:11px;
            color:var(--dim)}
  .modeline select{background:var(--panel2);color:var(--amber);
            border:1px solid var(--line);border-radius:6px;
            font:11px var(--mono);padding:4px 6px}

  /* status */
  #status{margin:18px 2px 8px;font-family:var(--mono);font-size:12px;
          color:var(--dim);min-height:16px}
  #status.err{color:var(--red)}
  #status.run{color:var(--amber)}
  #status.ok{color:#f2ca4c;font-weight:600}
  .bar{height:3px;background:var(--line);border-radius:2px;overflow:hidden;
       margin-bottom:18px}
  .bar i{display:block;height:100%;width:0;background:var(--mag);
       transition:width .4s}

  /* clips */
  .clip{display:flex;align-items:center;gap:12px;background:var(--panel);
        border:1px solid var(--line);border-radius:10px;padding:10px 12px;
        margin-bottom:10px}
  .clip button.play{width:38px;height:38px;border-radius:50%;
        background:var(--mag-soft);color:var(--mag);font-size:14px;
        flex:none}
  .clip button.play.on{background:var(--mag);color:#1a0d16}
  .clip .wave{position:relative;flex:1;height:38px;min-width:0}
  .clip canvas{position:absolute;inset:0;height:38px;width:100%}
  .clip .wave{cursor:crosshair}
  .clip .sel{position:absolute;top:0;bottom:0;background:var(--mag-soft);
         border-left:2px solid var(--mag);border-right:2px solid var(--mag);
         pointer-events:none;display:none}
  .clip .playhead{position:absolute;top:0;left:0;width:2px;height:100%;
        background:var(--amber);box-shadow:0 0 6px var(--amber);
        pointer-events:none;transition:left .05s linear}
  .meta{flex:none;text-align:right;font-family:var(--mono);font-size:10px;
        color:var(--dim);line-height:1.5}
  .clip button.del{flex:none;width:30px;height:30px;border-radius:6px;
        background:transparent;color:var(--dim);font-size:15px}
  .clip button.del:hover{color:var(--red);background:#c25b4e22}

  .empty{font-family:var(--mono);font-size:12px;color:var(--dim);
         padding:30px 0;text-align:center}

  #toolbar{display:flex;align-items:center;gap:14px;margin:0 2px 14px}
  #toolbar .selall{display:flex;align-items:center;gap:7px;
         font-family:var(--mono);font-size:11px;letter-spacing:.08em;
         color:var(--dim);cursor:pointer}
  #toolspacer{flex:1}
  #keepdest{font-family:var(--mono);font-size:10px;color:var(--dim)}
  #save{background:var(--mag);color:#1a0d16;padding:8px 16px}
  #save:disabled{background:var(--line);color:var(--dim);cursor:default}
  #delsel{background:transparent;border:1px solid #c25b4e55;color:var(--red);padding:8px 16px}
  #delsel:hover:not(:disabled){background:#c25b4e22}
  #delsel:disabled{background:var(--line);border-color:transparent;color:var(--dim);cursor:default}
  .guide{background:var(--panel);border:1px solid var(--line);border-radius:10px;
         margin:0 0 14px;font-size:13px;color:var(--dim)}
  .guide>summary{cursor:pointer;list-style:none;padding:11px 16px;
         font-family:var(--mono);font-size:11px;letter-spacing:.12em;color:var(--dim)}
  .guide>summary::-webkit-details-marker{display:none}
  .guide>summary::before{content:"▸ ";color:var(--mag);font-size:16px;vertical-align:-1px}
  .guide[open]>summary::before{content:"▾ "}
  .guide>summary:hover{color:var(--text)}
  .guide .gbody{padding:2px 18px 16px;line-height:1.55}
  .guide .gbody h4{color:var(--text);font-family:var(--mono);font-size:10px;
         letter-spacing:.12em;margin:16px 0 6px;font-weight:600}
  .guide .gbody b{color:var(--text);font-weight:600}
  .guide .gbody i{color:var(--dim);font-style:italic}
  .guide .gbody code{font-family:var(--mono);font-size:12px;color:var(--mag);
         background:var(--panel2);padding:1px 5px;border-radius:4px}
  .guide .gbody ul{margin:4px 0;padding-left:18px}
  .guide .gbody li{margin:3px 0}
  .guide .gbody p{margin:4px 0}
  .clip .pick{flex:none;width:17px;height:17px;accent-color:var(--mag);
         cursor:pointer}
  .clip.saved{border-color:var(--mag-soft)}
  .clip .tick{flex:none;font-family:var(--mono);font-size:10px;
         color:var(--mag);width:14px;text-align:center}
  input[type=checkbox]{accent-color:var(--mag)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>L<span class="o">O</span>OP LAB</h1>
    <span class="sub">magenta rt2 · local</span>
  </header>

  <div class="console">
    <div class="promptrow">
      <input id="prompt" placeholder="describe the loop — e.g. techno drum loop, dusty 909, rolling sub"
             autocomplete="off">
      <button id="go">Generate</button>
    </div>

    <div class="bank">
      <div class="fader"><label>OUTPUTS</label>
        <input type="range" id="outputs" min="1" max="10" value="4">
        <div class="val"><span id="outputs-v">4</span> <em>clips</em></div></div>
      <div class="fader"><label>LENGTH</label>
        <input type="range" id="duration" min="2" max="20" step="1" value="8">
        <div class="val"><span id="duration-v">8</span> <em>seconds</em></div></div>
      <div class="fader"><label>RANDOMNESS</label>
        <input type="range" id="temperature" min="0.6" max="1.6" step="0.05" value="1.05">
        <div class="val"><span id="temperature-v">1.05</span> <em>temp</em></div></div>
      <div class="fader"><label>COMPLEXITY</label>
        <input type="range" id="top_k" min="20" max="280" step="10" value="130">
        <div class="val"><span id="top_k-v">130</span> <em>top-k</em></div></div>
    </div>

    <div class="modeline">
      <span>model
        <select id="model">
          <option value="mrt2_small">mrt2_small · fast</option>
          <option value="mrt2_base">mrt2_base · quality</option>
        </select>
      </span>
      <span id="eta"></span>
    </div>
  </div>

  <details class="guide">
    <summary>guide</summary>
    <div class="gbody">
      <h4>THE FADERS</h4>
      <ul>
        <li><b>Outputs</b> — how many variations you get in one batch.</li>
        <li><b>Length</b> — clip length in seconds.</li>
        <li><b>Randomness</b> — higher wanders further from the obvious take; lower stays safe and repeatable.</li>
        <li><b>Complexity</b> — higher is busier, more ideas at once; lower is sparser and steadier.</li>
      </ul>
      <h4>WRITING PROMPTS</h4>
      <ul>
        <li>Lead with genre and feel: <code>dusty boom-bap drum loop, warm sub</code>.</li>
        <li>To steer away from singing, start with <code>instrumental</code> and lean on cues like <i>drum loop, percussion, dub techno, ambient</i>.</li>
        <li>Words like <i>soul, pop, gospel, anthem</i> invite vocals — skip them if you want none.</li>
      </ul>
      <h4>ABOUT VOCALS</h4>
      <p>Magenta sometimes adds mumbled vocal artefacts even on instrumental prompts — it's a quirk of the model, and no fader removes it. If a clip is good apart from that, crop a clean bar or two in your DAW.</p>
      <h4>KEEPING &amp; BINNING</h4>
      <ul>
        <li>Tick the good ones, then <b>Save selected</b> — they copy to your keep folder.</li>
        <li><b>Delete selected</b> bins the rest; deleted clips go to the Trash, so they're recoverable.</li>
      </ul>
    </div>
  </details>

  <div id="status"></div>
  <div class="bar"><i id="barfill"></i></div>

  <div id="toolbar">
    <label class="selall"><input type="checkbox" id="selall"> select all</label>
    <span id="toolspacer"></span>
    <span id="keepdest"></span>
    <button id="delsel" disabled>Delete selected</button>
    <button id="save" disabled>Save selected</button>
  </div>
  <div id="clips"></div>
</div>

<script>
const $ = id => document.getElementById(id);
const sliders = ["outputs","duration","temperature","top_k"];
let audioCtx, currentAudio = null, currentBtn = null, currentFile = null, raf = null;

function startPlayhead(ph, dur){
  if (raf) cancelAnimationFrame(raf);
  const frame = () => {
    if (!currentAudio){ raf = null; return; }
    const d = currentAudio.duration || dur || 1;
    ph.style.left = ((currentAudio.currentTime % d) / d * 100) + "%";
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
}

sliders.forEach(s => $(s).addEventListener("input", () => {
  $(s+"-v").textContent = $(s).value;
}));

async function generate(){
  const body = { prompt: $("prompt").value, model: $("model").value,
    outputs:+$("outputs").value, duration:+$("duration").value,
    temperature:+$("temperature").value, top_k:+$("top_k").value };
  const r = await fetch("/api/generate", {method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const j = await r.json();
  if (j.error) setStatus(j.error, "err"); else poll();
}
$("go").addEventListener("click", generate);
$("prompt").addEventListener("keydown", e => { if(e.key==="Enter") generate(); });

function setStatus(msg, cls){ const s=$("status");
  s.textContent = msg; s.className = cls || ""; }

const selected = new Set();
const regions = new Map();  // file -> {start, end} as 0..1 fractions of the clip
let keepDest = "";

function refreshToolbar(){
  const n = selected.size;
  $("save").disabled = n === 0;
  $("save").textContent = n ? `Save ${n} selected` : "Save selected";
  $("delsel").disabled = n === 0;
  $("delsel").textContent = n ? `Delete ${n} selected` : "Delete selected";
  const boxes = document.querySelectorAll(".clip .pick");
  const all = boxes.length > 0 && [...boxes].every(b => b.checked);
  $("selall").checked = all;
}

$("selall").addEventListener("change", () => {
  const on = $("selall").checked;
  document.querySelectorAll(".clip .pick").forEach(b => {
    b.checked = on;
    if (on) selected.add(b.dataset.file); else selected.delete(b.dataset.file);
  });
  refreshToolbar();
});

$("save").addEventListener("click", async () => {
  if (!selected.size) return;
  $("save").disabled = true;
  const regObj = {};
  for (const f of selected) if (regions.has(f)) regObj[f] = regions.get(f);
  const r = await fetch("/api/keep", {method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({files:[...selected], regions: regObj})});
  const j = await r.json();
  if (j.error){ setStatus(j.error, "err"); }
  else { setStatus(`Saved ${j.saved} to ${j.dest}`, "ok"); selected.clear(); }
  loadClips();
});

$("delsel").addEventListener("click", async () => {
  if (!selected.size) return;
  const files = [...selected];
  if (!confirm(`Delete ${files.length} clip${files.length>1?"s":""}? (moved to Trash)`)) return;
  $("delsel").disabled = true;
  if (currentFile && files.includes(currentFile)) stopPlayback();
  for (const f of files){
    regions.delete(f);
    await fetch("/api/clips/" + encodeURIComponent(f), {method:"DELETE"});
  }
  selected.clear();
  setStatus(`Deleted ${files.length} to Trash`);
  loadClips();
});

let polling = false;
async function poll(){
  if (polling) return; polling = true;
  $("go").disabled = true;
  while (true){
    const st = await (await fetch("/api/status")).json();
    if (st.error){ setStatus(st.error, "err"); $("barfill").style.width=0; break; }
    if (st.busy){
      setStatus(st.message, "run");
      $("barfill").style.width = (st.total? (st.done/st.total)*100:0) + "%";
      await new Promise(r => setTimeout(r, 1500));
    } else {
      setStatus(st.message || "");
      $("barfill").style.width = 0;
      break;
    }
  }
  polling = false; $("go").disabled = false;
  loadClips();
}

async function loadClips(){
  const j = await (await fetch("/api/clips")).json();
  if (j.keepers){ keepDest = j.keepers; $("keepdest").textContent = "→ " + j.keepers; }
  const box = $("clips"); box.innerHTML = "";
  if (!j.clips.length){
    box.innerHTML = '<div class="empty">no clips yet — type a prompt and slide a fader</div>';
    if (currentFile) stopPlayback();
    refreshToolbar();
    return;
  }
  for (const c of j.clips) box.appendChild(clipRow(c));
  rebindPlayback();
  refreshToolbar();
}

function stopPlayback(){
  if (raf){ cancelAnimationFrame(raf); raf = null; }
  if (currentAudio){ currentAudio.pause(); currentAudio = null; }
  if (currentBtn){
    currentBtn.classList.remove("on"); currentBtn.textContent = "▶";
    const ph = currentBtn.closest(".clip")?.querySelector(".playhead");
    if (ph) ph.style.left = "0%";
    currentBtn = null;
  }
  currentFile = null;
}

// After the list redraws, re-attach controls to whichever clip is still
// playing (its old button was just destroyed). If that clip is gone, stop.
function rebindPlayback(){
  if (!currentFile || !currentAudio){ return; }
  const row = [...document.querySelectorAll(".clip")].find(
    r => r.querySelector(".pick")?.dataset.file === currentFile);
  if (!row){ stopPlayback(); return; }
  currentBtn = row.querySelector(".play");
  currentBtn.classList.add("on"); currentBtn.textContent = "■";
  startPlayhead(row.querySelector(".playhead"), null);
}

function clipRow(c){
  const row = document.createElement("div"); row.className = "clip";
  if (c.saved) row.classList.add("saved");

  const pick = document.createElement("input");
  pick.type = "checkbox"; pick.className = "pick"; pick.dataset.file = c.file;
  pick.checked = selected.has(c.file);
  pick.addEventListener("change", () => {
    if (pick.checked) selected.add(c.file); else selected.delete(c.file);
    refreshToolbar();
  });

  const play = document.createElement("button");
  play.className = "play"; play.textContent = "▶";
  const wave = document.createElement("div"); wave.className = "wave";
  const cv = document.createElement("canvas");
  const sel = document.createElement("div"); sel.className = "sel";
  const ph = document.createElement("div"); ph.className = "playhead";
  wave.append(cv, sel, ph);
  const meta = document.createElement("div"); meta.className = "meta";
  meta.innerHTML = `${c.prompt.slice(0,28)}<br>t ${c.temp} · k ${c.top_k} · ${c.duration|0}s`;
  const tick = document.createElement("div"); tick.className = "tick";
  tick.textContent = c.saved ? "✓" : "";
  tick.title = c.saved ? "saved to keepers" : "";
  const del = document.createElement("button");
  del.className = "del"; del.textContent = "✕";
  row.append(pick, play, wave, meta, tick, del);

  const url = "/clips/" + encodeURIComponent(c.file);
  drawWave(cv, url);

  // --- region selection (drag on the waveform) ---
  function paintSel(){
    const r = regions.get(c.file);
    if (r){ sel.style.display = "block"; sel.style.left = (r.start*100)+"%";
            sel.style.width = ((r.end-r.start)*100)+"%"; }
    else { sel.style.display = "none"; }
  }
  paintSel();
  let dragging = false, dragStart = 0, moved = false;
  const fracAt = e => {
    const rect = wave.getBoundingClientRect();
    return Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  };
  wave.addEventListener("pointerdown", e => {
    e.preventDefault();
    dragging = true; moved = false; dragStart = fracAt(e); wave.setPointerCapture(e.pointerId);
  });
  wave.addEventListener("pointermove", e => {
    if (!dragging) return;
    const x = fracAt(e);
    if (Math.abs(x - dragStart) > 0.004) moved = true;
    if (moved){ regions.set(c.file, {start: Math.min(dragStart, x), end: Math.max(dragStart, x)}); paintSel(); }
  });
  wave.addEventListener("pointerup", () => {
    dragging = false;
    if (!moved){ regions.delete(c.file); paintSel(); }  // a plain click (no drag) always clears
    else { const r = regions.get(c.file); if (r && (r.end - r.start) < 0.01){ regions.delete(c.file); paintSel(); } }
    if (currentFile === c.file && currentAudio) currentAudio.loop = !regions.get(c.file);
  });

  play.addEventListener("click", () => {
    if (currentBtn === play){ stopPlayback(); return; }
    stopPlayback();
    currentAudio = new Audio(url); currentBtn = play; currentFile = c.file;
    const reg = regions.get(c.file);
    currentAudio.loop = !reg;  // whole-clip loop only when no region is set
    if (reg) currentAudio.addEventListener("loadedmetadata", () => {
      currentAudio.currentTime = reg.start * currentAudio.duration;
    });
    currentAudio.addEventListener("timeupdate", () => {
      if (!currentAudio) return;
      const r = regions.get(c.file);
      if (r){
        const d = currentAudio.duration || c.duration;
        if (currentAudio.currentTime >= r.end * d) currentAudio.currentTime = r.start * d;
      }
    });
    currentAudio.addEventListener("ended", () => {
      const r = regions.get(c.file);   // region ending at the clip end: loop back on 'ended'
      if (currentAudio && r){
        currentAudio.currentTime = r.start * (currentAudio.duration || c.duration);
        currentAudio.play();
      }
    });
    currentAudio.play();
    play.classList.add("on"); play.textContent = "■";
    startPlayhead(ph, c.duration);
  });

  del.addEventListener("click", async () => {
    if (currentBtn === play) stopPlayback();
    selected.delete(c.file); regions.delete(c.file);
    await fetch("/api/clips/" + encodeURIComponent(c.file), {method:"DELETE"});
    loadClips();
  });
  return row;
}

async function drawWave(canvas, url){
  try{
    if (!canvas.clientWidth){            // not laid out yet — retry next frame
      requestAnimationFrame(() => drawWave(canvas, url)); return;
    }
    audioCtx = audioCtx || new (window.AudioContext||window.webkitAudioContext)();
    const buf = await (await fetch(url)).arrayBuffer();
    const audio = await audioCtx.decodeAudioData(buf);
    const data = audio.getChannelData(0);
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth * dpr, h = canvas.clientHeight * dpr;
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d");
    const bars = Math.floor(w / (3*dpr));
    const step = Math.floor(data.length / bars);
    ctx.fillStyle = "#d6418f";
    for (let i=0;i<bars;i++){
      let peak = 0;
      for (let j=0;j<step;j+=16) peak = Math.max(peak, Math.abs(data[i*step+j]||0));
      const bh = Math.max(2*dpr, peak * h);
      ctx.fillRect(i*3*dpr, (h-bh)/2, 2*dpr, bh);
    }
  }catch(e){ /* leave canvas blank on decode failure */ }
}

loadClips(); poll();
</script>
</body>
</html>"""


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


if __name__ == "__main__":
    print(f"\n  Loop Lab → http://localhost:{PORT}")
    print(f"  Keepers  → {pretty_path(KEEPERS_DIR)}")
    if shutil.which("mrt") is None:
        print("\n  WARNING: `mrt` is not on your PATH.")
        print("  Activate the virtualenv where you installed magenta-rt first,")
        print("  then restart. See the README for setup.")
    elif not OUTPUTS_DIR.exists():
        print(f"\n  WARNING: no model output folder at {pretty_path(MAGENTA_DIR)}.")
        print("  Run `mrt models init` then `mrt models download`, or set")
        print("  LOOP_LAB_MAGENTA_HOME to your install. See the README.")
    print()
    app.run(host="127.0.0.1", port=PORT, debug=False)
