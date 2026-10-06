<div align="center">

```
 █████╗  ██████╗ ███╗   ██╗██╗   ██╗██╗  ██╗
██╔══██╗██╔═══██╗████╗  ██║╚██╗ ██╔╝╚██╗██╔╝
███████║██║   ██║██╔██╗ ██║ ╚████╔╝  ╚███╔╝
██╔══██║██║   ██║██║╚██╗██║  ╚██╔╝   ██╔██╗
██║  ██║╚██████╔╝██║ ╚████║   ██║   ██╔╝ ██╗
╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
```

### NEURAL CORE // ONLINE

**A local-first AI assistant for your desktop. It listens, reasons, acts, and remembers, entirely on your machine.**

![Platform](https://img.shields.io/badge/platform-Windows%2011-083fc3?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-2f6bff?style=flat-square)
![LLM](https://img.shields.io/badge/LLM-Ollama%20%2F%20llama3-5b8cff?style=flat-square)
![Privacy](https://img.shields.io/badge/runs-100%25%20local-052a82?style=flat-square)
![Status](https://img.shields.io/badge/status-complete-031a52?style=flat-square)

</div>

---

## // OVERVIEW

Aonyx is a voice-driven AI assistant that lives on your desktop and appears the moment you call it. Press a hotkey, speak, and a holographic neural core wakes up, reacting in real time to your voice, its own thinking, and the tools it uses.

It is not a chatbot wrapped in a window. Behind the HUD sits an orchestration layer that decides what you want, chooses whether a tool is needed, executes it through a strict allowlist, observes the real result, and only then responds. It does not invent tool results, and it cannot run arbitrary commands.

Everything runs locally: speech recognition, language model, speech synthesis, and memory. No cloud account, no telemetry, no data leaving your machine except the web lookups you explicitly allow.

---

## // CAPABILITIES

| Module | What it does |
| --- | --- |
| **Holographic Core** | A real-time 3D neural core (WebGL) that reacts to microphone level, thinking, tool use, speech output, and errors |
| **Voice Interface** | Push-to-talk, local speech-to-text, streamed text-to-speech, and instant barge-in to interrupt mid-sentence |
| **AI Orchestration** | Intent, tool selection, execution, observation, reasoning, response, in a multi-step loop with hard limits |
| **Persistent Memory** | SQLite-backed memory for short-term context, long-term facts, preferences, and task state |
| **Desktop Intelligence** | Active window awareness, safe application launching, and live system telemetry |
| **Web Intelligence** | Web search and page fetching with SSRF protection and prompt-injection defense |
| **Personality Layer** | Calm, concise, and precise. Response length adapts to the task |
| **Raycast-style Launcher** | A global hotkey summons or hides the HUD instantly. Rendering pauses while hidden |

---

## // HOW IT THINKS

```
        USER INPUT  (voice or text)
             |
             v
     +----------------+
     |  INTENT        |   what is being asked?
     +-------+--------+
             |
             v
     +----------------+        no
     |  NEED A TOOL?  +--------------------+
     +-------+--------+                    |
             | yes                         |
             v                             |
     +----------------+                    |
     |  SELECT TOOL   |                    |
     +-------+--------+                    |
             v                             |
     +----------------+                    |
     |  VALIDATE +    |   schema check,    |
     |  PERMISSION    |   allowlist,       |
     +-------+--------+   confirmation     |
             v                             |
     +----------------+                    |
     |  EXECUTE       |                    |
     +-------+--------+                    |
             v                             |
     +----------------+                    |
     |  OBSERVE       |   real result      |
     +-------+--------+   only             |
             |                             |
             +-------> REASON <------------+
                          |
                          v
                       RESPOND  ->  streamed text  ->  spoken audio
```

The loop repeats until the model answers without requesting another tool, with a hard cap on steps and a time budget. If a tool fails, Aonyx reports the actual failure instead of inventing a result.

### State machine

```
IDLE --> LISTENING --> THINKING --> TOOL_EXECUTION --> THINKING --> SPEAKING --> IDLE
                           |                |                          |
                           +----------------+---------> ERROR <--------+
                                                          |
                                                          +--> retry / settle to IDLE
```

The 3D core maps directly to these states. Each state changes how the core moves, glows, and pulses, and the core never fully stops moving.

---

## // SECURITY MODEL

Aonyx is designed on the assumption that a language model should never be trusted with unrestricted access.

- **Explicit tool allowlist.** The model can only call registered tools. There is no shell tool, no `eval`, and no "run command" capability, by design.
- **Schema validation.** Every tool call is validated against its input schema. Malformed or extra arguments are rejected.
- **Permission levels.** Tools are classified as safe, confirm, or blocked. Anything that touches your files, apps, or the web asks for confirmation in the HUD first.
- **Application allowlist.** The model supplies an app key, never a path or command line. Launches use argument lists with `shell=False`.
- **SSRF protection.** Web tools refuse localhost, private, and internal network addresses.
- **Prompt-injection defense.** Web pages, files, and memory contents are treated as untrusted data, wrapped, and flagged so instructions hidden inside them are not followed.
- **Audit trail.** Tool calls are logged with their arguments, permission result, duration, and outcome. File contents and secrets are not logged.
- **Privacy by default.** The microphone records only while listening, and the HUD shows whenever audio is being captured.

---

## // ARCHITECTURE

```
+---------------------------------------------------------------+
|                         AONYX HUD                             |
|     React + TypeScript + Three.js (React Three Fiber)        |
|     Tailwind  /  Zustand  /  GLSL holographic core            |
+--------------------------+------------------------------------+
                           |  pywebview JS bridge
                           |  (thread-safe events)
+--------------------------v------------------------------------+
|                      PYTHON BACKEND                           |
|                                                               |
|   Window manager + global hotkeys (Win32)                     |
|   Orchestrator  ->  Tool registry  ->  Executors              |
|   Memory manager (SQLite)                                     |
|   Voice pipeline: capture -> STT -> TTS (gapless, interruptible)
|   Provider interface (Ollama today, swappable later)          |
+--------------+------------------------------+-----------------+
               |                              |
        +------v------+                +------v-------+
        |   OLLAMA    |                |  LOCAL AUDIO |
        |  llama3     |                |  mic / speakers
        +-------------+                +--------------+
```

The language model sits behind a provider interface, so the orchestrator, tools, and UI never depend on Ollama directly. Replacing the model means writing one adapter.

---

## // TECH STACK

| Layer | Technology |
| --- | --- |
| Desktop shell | Python, pywebview (WebView2), Win32 APIs via ctypes |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Zustand |
| 3D rendering | Three.js, React Three Fiber, custom GLSL |
| Language model | Ollama (llama3), behind a provider-independent interface |
| Speech-to-text | faster-whisper, running locally |
| Text-to-speech | Windows SAPI5, with sentence-level streaming |
| Audio capture | sounddevice |
| Memory | SQLite |
| Testing | pytest |

---

## // GETTING STARTED

### Requirements

- Windows 10 or 11 (the launcher, hotkeys, and window handling use Win32)
- Python 3.10 or newer
- Node.js 18 or newer
- [Ollama](https://ollama.com) installed and running
- A working microphone and speakers

### Install

```bash
# 1. Clone
git clone https://github.com/<your-username>/aonyx.git
cd aonyx

# 2. Pull the language model
ollama pull llama3

# 3. Python environment
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 4. Build the HUD
cd frontend
npm install
npm run build
cd ..

# 5. Configure
copy .env.example .env
```

### Run

```bash
pythonw aonyx_app.pyw
```

Aonyx starts in the background. Press the summon hotkey to bring up the HUD.

For development, run `npm run dev` inside `frontend/` and `python aonyx_app.pyw` for the launcher. Use `python` instead of `pythonw` to see console output.

---

## // CONTROLS

| Action | Default |
| --- | --- |
| Summon or hide the HUD | `Ctrl + Shift + Space` |
| Push-to-talk | `Ctrl + Alt + Space` |
| Cancel, interrupt speech, or hide | `Esc` |
| Command history | `Up` / `Down` |

Both hotkeys are configurable in `.env`. If a hotkey conflicts with another application, Aonyx shows a warning in the HUD.

---

## // CONFIGURATION

Settings live in `.env` and the config file. Key options:

| Setting | Purpose |
| --- | --- |
| `OLLAMA_HOST` | Ollama address, default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Model name, default `llama3:latest` |
| Push-to-talk key | Hotkey used for voice input |
| Input device | Microphone selection |
| Allowed apps | The application launch allowlist |
| Allowed folders | Folders the file tools may read |
| Tool limits | Maximum steps and timeouts per request |

---

## // EXTENDING AONYX

Adding a tool means registering a name, description, input schema, execution function, and a safety level. The registry exposes it to the model automatically, validates its arguments, and applies the confirmation rules for its permission level.

```python
@registry.tool(
    name="get_current_time",
    description="Return the current local date and time.",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
    permission="safe",
    timeout=2,
)
def get_current_time(args):
    ...
```

Tools that touch the filesystem, launch programs, or reach the network should use the confirm level and validate every input.

---

## // PROJECT STRUCTURE

```
aonyx/
    app/
        orchestrator/       multi-step reasoning loop and provider interface
        tools/              tool registry and allowlisted executors
        memory/             SQLite memory manager
        voice/              capture, speech-to-text, text-to-speech
    frontend/
        src/
            components/     3D core, command bar, panels, event feed
            store/          Zustand state machine
    tests/                  pytest suites
    aonyx_app.pyw           launcher, window manager, global hotkeys
    .env.example
    README.md
```

---

## // TESTING

```bash
pytest
```

The suites cover audio chunking and gapless playback timing, web tool security (SSRF, private addresses, malformed URLs), desktop and process safety, and memory persistence across restarts.

---

## // KNOWN LIMITATIONS

- Windows only. The launcher and hotkeys rely on Win32 APIs.
- Tool selection quality depends on the model. llama3 is workable for structured tool use, but a stronger tool-capable model will be more reliable.
- Speech synthesis uses the Windows SAPI5 voices installed on your system, so voice quality varies by machine.
- The compact orb is an opaque window. True transparency with WebGL is unreliable on WebView2.

---

## // LICENSE

Add your license here, for example MIT.

---

<div align="center">

**AONYX** // built local, runs local, stays yours.

</div>
