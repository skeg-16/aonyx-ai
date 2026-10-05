# Aonyx (JARVIS) Project Master Plan & State

## Current State (As of End of Session)
- **Phase 1 (Core Foundation)**: COMPLETED.
- **Phase 2 (JARVIS HUD)**: COMPLETED.
- **Phase 3 (3D AI Core)**: COMPLETED.
- **Phase 4 (Voice Interface)**: COMPLETED.
- **Phase 5 (AI Orchestration)**: COMPLETED.
  - Built a robust orchestration engine (`app/orchestrator/`) capable of multi-step tool execution.
  - Enforced a strict JSON communication schema for the LLM.
  - Resolved `input overflow` blocking issues on Windows.
  - Fixed JSON streaming bugs, and thread-safe UI updates.

---

## Roadmap (Next Steps for Tomorrow)

### 6. PHASE 6 — PERSISTENT MEMORY
Implement a structured memory system.
- Separate memory into: SHORT-TERM CONTEXT, LONG-TERM MEMORY, USER PREFERENCES, TASK MEMORY.
- Do not simply dump the entire conversation into every Ollama request. Create memory retrieval.
- Example: USER: "Remember that I prefer dark interfaces." -> Store structured memory. Later: USER: "Make the interface match my preference." -> Retrieve relevant memory.
- Requirements: local storage, searchable memory, memory relevance, explicit save/delete, no silent fabrication, conversation context management.
- Create a memory manager abstraction.
- The AI should be able to request: `STORE_MEMORY`, `RETRIEVE_MEMORY`, `UPDATE_MEMORY` (but storage remains controlled by the application).
- Add a small memory/status indicator to the HUD.
- Test persistence by restarting the application.

### 7. PHASE 7 — DESKTOP INTELLIGENCE
Give the assistant controlled awareness of the computer.
- Implement safe tools for: active application, system information, CPU usage, RAM usage, disk usage, battery, network status, time/date, currently available files, opening approved applications, opening approved URLs.
- Expose selected information through the HUD.
- Create a futuristic system monitor around the 3D AI core (e.g., CPU 23%, MEMORY 61%, NETWORK ONLINE, OLLAMA ONLINE, MIC ONLINE, TTS ONLINE).
- The AI should be able to answer questions like: "What's using my memory?", "Is Ollama running?", "What applications are open?", "How much storage do I have?"
- Do not give the LLM unrestricted operating-system access. Every desktop action must pass through an explicit tool.
- Ask for confirmation before potentially destructive actions.

### 8. PHASE 8 — WEB INTELLIGENCE
Add controlled internet capabilities (Only after local system is stable).
- The assistant should be able to: search the web, retrieve relevant information, summarize results, compare information, cite sources, distinguish retrieved information from its own reasoning.
- Do not pretend the local LLM knows current information.
- When current information is required: USER -> WEB SEARCH -> RETRIEVE SOURCES -> AI ANALYSIS -> ANSWER WITH SOURCES.
- The UI should show when the assistant is: SEARCHING, READING, ANALYZING, RESPONDING.
- Keep web access modular. The local Ollama model remains the reasoning engine where appropriate.
- Do not automatically browse for every question.

### 9. PHASE 9 — ASSISTANT PERSONALITY
Develop the assistant's interaction style.
- The assistant should feel: intelligent, calm, concise, observant, confident, helpful, slightly futuristic, natural.
- Avoid: excessive jokes, cringe "JARVIS" catchphrases, constantly saying "Sir", unnecessarily long responses, pretending to have consciousness, pretending to have capabilities it does not have.
- The assistant should adapt response length to the task (Simple request: short response. Complex request: structured response. Technical task: precise response).
- The personality must be implemented separately from the core orchestration logic.
- Create configurable personality settings. Do not hardcode the entire personality into application logic.

### 10. PHASE 10 — FINAL JARVIS EXPERIENCE (The "WOW" Layer)
Polish the entire application into a cohesive futuristic AI operating system.
- Do not add random effects. Everything must communicate purpose.
- Add where appropriate: 3D AI core improvements, particle reactions, audio-reactive visualization, holographic panels, subtle scan lines, system telemetry, contextual information, smooth transitions, intelligent notifications, tool execution visualization, voice waveform, AI status visualization, dynamic environment indicators, compact HUD mode, expanded command center.
- Create a visual hierarchy:
  - CENTER: 3D AI core
  - AROUND CORE: AI state / activity
  - SECONDARY: system status
  - LOWER AREA: conversation / command
  - OPTIONAL: tool activity / context
- The interface should look like a unified AI system rather than a collection of widgets.
- Performance is more important than visual complexity.
- Target a polished, production-quality experience.

Before declaring the project complete:
- Perform a full end-to-end test: TEXT, VOICE, OLLAMA, MEMORY, TOOLS, DESKTOP INFORMATION, WEB SEARCH, 3D VISUALIZATION, HIDE/SHOW, HOTKEY, ERROR RECOVERY, APPLICATION RESTART.
- Document every PASS / FAIL / NOT TESTED result.
- Do not claim completion for anything that was not actually tested on the real desktop application.
# Update Report (2026-10-04)
- Fixed `ALLOWED_APPS` entries: Notepad now uses absolute path, Calculator uses `calc.exe`.
- Switched app launch method in `tools.py` to `subprocess.Popen(['cmd', '/c', 'start', '', target])` for reliable foreground window opening.
- Disabled always‑on‑top flag in `main.py` so Alt+Tab works normally.
- Added diagnostic scripts (`test_os_system.py`, `test_startfile.py`) for quick verification.
- After restarting the PC and `python main.py`, all allowed apps (Notepad, Calculator, Chrome, Discord, Spotify, FxSound, Edge, VS Code, Paint, etc.) should open correctly.
- Next step: restart the system, run JARVIS, and confirm each app appears.

# Update Report (2026-10-05)
- Fixed test harness (`test_suite.py` guard) and calculator AST handling.
- Added `safe_print` to `tool_sanity_test.py` to avoid UnicodeEncodeError.
- All automated tests now pass (`pytest -vv`): 1 passed, 5 warnings.
- Desktop app (`main.py`) runs; UI loads with hotkeys and rounded corners.
- Frontend `index.html` served via local HTTP server; screenshots captured for desktop and mobile.
- Ready to continue with Phase 6 tomorrow.

