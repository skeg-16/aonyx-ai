import asyncio
import json
import threading
import logging
import sys
import time
import re
from collections import deque
from .llm import OllamaClient
from .voice import VoiceEngine
from .speech_chunker import SpeechChunker, clean_for_speech
from .orchestrator.provider import OllamaProvider
from .orchestrator.engine import Orchestrator
from .orchestrator.registry import registry, ToolPermission

logger = logging.getLogger(__name__)


class _UIBus:
    """Single ordered channel Python -> frontend.

    All UI events go through one thread so ordering is preserved (segment queued -> start -> end ->
    utterance done) and high-frequency events (RMS / speech ticks) are coalesced instead of piling
    up behind a slow evaluate_js call.
    """

    def __init__(self, get_window):
        self._get_window = get_window
        self._q = deque()
        self._keyed = {}
        self._cv = threading.Condition()
        threading.Thread(target=self._run, name="ui-bus", daemon=True).start()

    def emit(self, name, detail, key=None):
        with self._cv:
            if key is not None and key in self._keyed:
                self._keyed[key]["detail"] = detail
                return
            item = {"name": name, "detail": detail, "key": key}
            if key is not None:
                self._keyed[key] = item
            self._q.append(item)
            self._cv.notify()

    def _run(self):
        while True:
            with self._cv:
                while not self._q:
                    self._cv.wait()
                item = self._q.popleft()
                if item["key"] is not None:
                    self._keyed.pop(item["key"], None)
            window = self._get_window()
            if window is None:
                continue
            try:
                js = (f'window.dispatchEvent(new CustomEvent({json.dumps(item["name"])}, '
                      f'{{detail: {json.dumps(item["detail"])}}}))')
                window.evaluate_js(js)
            except Exception as e:
                logger.debug(f"UI emit failed ({item['name']}): {e}")


def _unescape_json_fragment(s: str) -> str:
    """Unescape the (possibly truncated) body of a JSON string that is still streaming in."""
    s = re.sub(r'\\u[0-9a-fA-F]{0,3}$', '', s)      # incomplete \uXXXX at the tail
    if re.search(r'(?<!\\)(?:\\\\)*\\$', s):         # lone trailing backslash (incomplete escape)
        s = s[:-1]

    def fix(m):
        c = m.group(1)
        if c.startswith('u'):
            try:
                return chr(int(c[1:], 16))
            except ValueError:
                return ''
        return {'n': '\n', 't': ' ', 'r': '', '"': '"', '\\': '\\', '/': '/'}.get(c, c)

    return re.sub(r'\\(u[0-9a-fA-F]{4}|.)', fix, s, flags=re.DOTALL)


class DesktopAPI:
    def __init__(self):
        self._window = None
        self.is_loaded = False
        self._llm = OllamaClient(host="127.0.0.1", port=11434, model="llama3:latest")
        self._pending_command = None
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self._loop = asyncio.new_event_loop()

        self._bus = _UIBus(lambda: self._window if (self._window and self.is_loaded) else None)
        self._last_state = None
        self._uid = 0
        self._task = None
        self._run_active = False
        self._run_uid = None
        self._errored = False
        self._chunker = SpeechChunker()
        self._last_clean_len = 0
        self._seg_idx = 0

        self._provider = OllamaProvider()
        ui_callbacks = {
            "set_state": self._orch_set_state,
            "show_tool_activity": self._show_tool_activity,
            "request_confirmation": self._request_confirmation,
            "stream_text": self._stream_text
        }
        self._orchestrator = Orchestrator(self._provider, ui_callbacks)

        self._voice_engine = VoiceEngine(self._on_voice_event)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        registry.register(
            "set_aonyx_visibility",
            "Hides or shows the Aonyx interface window.",
            {"type": "object", "properties": {"visible": {"type": "boolean"}}, "required": ["visible"]},
            ToolPermission.SAFE,
            self._set_visibility_tool
        )

    def _set_visibility_tool(self, args):
        visible = args.get("visible", True)
        if hasattr(self, '_hotkey_mgr') and self._hotkey_mgr:
            # Check current state
            currently_hidden = self._hotkey_mgr.is_hidden
            if visible and currently_hidden:
                # Need to use threadsafe call if we are manipulating UI
                self._loop.call_soon_threadsafe(self._hotkey_mgr.toggle_state)
            elif not visible and not currently_hidden:
                self._loop.call_soon_threadsafe(self._hotkey_mgr.toggle_state)
        return {"status": "ok", "data": f"Visibility set to {visible}.", "summary": f"Visibility set"}

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def set_window(self, window):
        self._window = window

    def on_loaded(self):
        self.is_loaded = True
        logger.info("Window loaded. Running init check.")
        asyncio.run_coroutine_threadsafe(self._init_check(), self._loop)

    async def _init_check(self):
        self._update_memory_count()
        is_healthy = await self._provider.health_check()
        if not is_healthy:
            self._set_state("ERROR", "Ollama is unavailable at 127.0.0.1:11434")
            return

        self._set_state("THINKING")
        self._set_message("System online. Warming up AI Core...")

        try:
            self._set_state("IDLE")
            self._set_message(f"System online. Orchestrator ready.")
        except Exception as e:
            self._set_state("ERROR", str(e))

    # ------------------------------------------------------------------ UI emitters
    def _emit(self, name, detail, key=None):
        self._bus.emit(name, detail, key)

    def _set_state(self, state: str, errorText: str = ""):
        if state != "ERROR" and state == self._last_state:
            return
        self._last_state = state
        self._emit("whis-state", {"state": state})
        if state == "ERROR" and errorText:
            self._emit("whis-error", {"errorText": errorText})

    def _orch_set_state(self, state: str, errorText: str = ""):
        """State changes coming from the orchestrator.

        SPEAKING is owned by the audio engine (it must reflect audible speech, not text generation),
        and the orchestrator's end-of-run IDLE must not cut off speech that is still playing.
        """
        if state == "SPEAKING":
            return
        if state == "IDLE" and self._voice_engine.is_busy():
            return
        self._set_state(state, errorText)

    def _set_message(self, message: str):
        self._emit("whis-message", {"message": message})

    def _show_tool_activity(self, tool_name: str, status: str):
        self._emit("whis-tool", {"name": tool_name, "status": status})

    def _request_confirmation(self, tool_name: str, args: dict):
        self._emit("whis-confirm", {"name": tool_name, "args": json.dumps(args)})

    # ------------------------------------------------------------------ LLM stream -> speech segments
    def _queue_segment(self, text: str, nl: bool):
        clean = clean_for_speech(text)
        if not clean:
            return
        idx = self._seg_idx
        self._seg_idx += 1
        uid = self._uid
        logger.info(f"Segment {idx} generated: {clean}")
        self._emit("whis-seg", {"uid": uid, "idx": idx, "text": clean, "nl": nl})
        self._voice_engine.speak(clean, uid, idx, nl)

    def _stream_text(self, chunk: str, full: str):
        match = re.search(r'"response"\s*:\s*"(.*)', full, re.DOTALL)
        if match:
            raw = match.group(1)
            # Remove trailing unescaped closing quote / brace
            raw = re.sub(r'(?<!\\)"\s*\}?\s*$', '', raw)
            clean_full = _unescape_json_fragment(raw)
        elif not full.lstrip().startswith('{'):
            clean_full = full            # plain-text message (e.g. "Max tool steps reached.")
        else:
            return

        if len(clean_full) < self._last_clean_len:     # a new generation started (e.g. retry)
            self._last_clean_len = 0
            self._chunker.reset()

        new_text = clean_full[self._last_clean_len:]
        if not new_text:
            return
        self._last_clean_len = len(clean_full)
        for seg_text, nl in self._chunker.feed(new_text):
            self._queue_segment(seg_text, nl)

    # ------------------------------------------------------------------ voice engine events
    def _on_voice_event(self, event_type, data):
        if event_type == "STATE":
            self._set_state(data)
        elif event_type == "RMS_UPDATE":
            src = "mic" if self._voice_engine.is_listening else "tts"
            self._emit("whis-rms", {"rms": data, "src": src}, key="rms")
        elif event_type == "SPEECH_TICK":
            self._emit("whis-speech", data, key="tick")
        elif event_type == "SEG_START":
            if getattr(self, '_run_uid', None) == data.get("uid") or getattr(self, '_uid', None) == data.get("uid"):
                self._display_text += data["text"] + ("\n\n" if data.get("nl") else " ")
                self._set_message(self._display_text)
            self._emit("whis-seg-start", data)
        elif event_type == "SEG_END":
            self._emit("whis-seg-end", data)
        elif event_type == "SEG_INSTANT":
            if getattr(self, '_run_uid', None) == data.get("uid") or getattr(self, '_uid', None) == data.get("uid"):
                self._display_text += data["text"] + ("\n\n" if data.get("nl") else " ")
                self._set_message(self._display_text)
            self._emit("whis-seg-instant", data)
        elif event_type == "UTT_DONE":
            self._emit("whis-utt", {"uid": data["uid"], "phase": "end", "reason": "complete"})
            self._emit("whis-rms", {"rms": 0, "src": "tts"}, key="rms")
            if (data["uid"] == self._uid and not self._run_active and not self._errored
                    and not self._voice_engine.is_listening):
                self._set_state("IDLE")
        elif event_type == "UTT_END":
            self._emit("whis-utt", {"uid": data["uid"], "phase": "end", "reason": data.get("reason", "interrupted")})
            self._emit("whis-rms", {"rms": 0, "src": "tts"}, key="rms")
            if not self._voice_engine.is_listening:
                self._set_state("THINKING" if self._run_active else "IDLE")
        elif event_type == "MIC_STATUS":
            self._emit("whis-mic", data)
        elif event_type == "NO_SPEECH":
            reason = (data or {}).get("reason")
            msgs = {
                "no_audio": "MIC // NO AUDIO CAPTURED. Check your microphone.",
                "no_speech": "MIC // NO SPEECH DETECTED. Try speaking closer to the microphone.",
                "empty_transcript": "Heard sound, but couldn't make out any words. Please try again.",
            }
            self._set_message(msgs.get(reason, "No speech detected."))
            self._set_state("IDLE")
        elif event_type == "TRANSCRIPT":
            logger.info(f"[CMD] transcript ready, submitting to orchestrator: {data}")
            self._loop.call_soon_threadsafe(self.send_message, data)
        elif event_type == "TTS_ERROR":
            logger.error(f"[TTS] {data}")
            self._emit("whis-voice", {"tts": "ERROR", "detail": str(data)})
        elif event_type == "VOICE_READY":
            self._emit("whis-voice", {"stt": "READY"})
        elif event_type == "VOICE_ERROR":
            self._set_state("ERROR", data)

    # ------------------------------------------------------------------ JS-accessible methods
    def toggle_listening(self):
        """Called from PTT hotkey, MIC button or core click."""
        if self._voice_engine.is_listening:
            logger.info("[MIC] listening stopped by user")
            self._voice_engine.stop_and_process("manual")
        else:
            if self._voice_engine.start_listening():
                self._set_state("LISTENING")
                self._set_message("Listening...")

    def stop_speaking(self):
        """Stops voice playback ONLY. The underlying task keeps running; its text still appears."""
        logger.info("STOP SPEAKING requested from UI.")
        self._voice_engine.interrupt_tts()

    def cancel_task(self):
        """Cancels the current orchestration (and silences speech). Distinct from stop_speaking."""
        logger.info("CANCEL TASK requested from UI.")
        self._voice_engine.interrupt_tts()
        self._loop.call_soon_threadsafe(self._cancel_run)

    def _cancel_run(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self._orchestrator.cancel()
        self._run_active = False
        self._set_message("Task cancelled.")
        self._set_state("IDLE")

    def send_message(self, text: str):
        """Called from the frontend (typed) or voice transcript."""
        logger.info(f"Received message from UI: {text}")
        self._start_request(text, f"User: {text}\n\nAonyx: ")

    def retry_last(self, text: str):
        logger.info(f"Retrying message from UI: {text}")
        self._start_request(text, f"User: {text}\n\nAonyx: ")

    def _start_request(self, text: str, display: str):
        self._uid += 1
        uid = self._uid
        self._display_text = display
        self._errored = False
        self._chunker.reset()
        self._last_clean_len = 0
        self._seg_idx = 0
        self._run_uid = uid
        self._voice_engine.begin_utterance(uid)       # also silences any previous speech
        self._emit("whis-run-start", {"uid": uid})
        self._emit("whis-utt", {"uid": uid, "phase": "start"})
        self._set_state("THINKING")
        self._set_message(display + "Thinking...")
        self._loop.call_soon_threadsafe(self._launch, text, uid)

    def _launch(self, text: str, uid: int):
        if self._task and not self._task.done():
            self._task.cancel()                       # drop the stale run before it can emit more text
        self._orchestrator.cancel()
        self._task = self._loop.create_task(self._process_message(text, uid))

    async def _process_message(self, text: str, uid: int, is_retry=False):
        lower_text = text.strip().lower()

        # System Commands Routing
        if lower_text == "/listen":
            self.toggle_listening()
            return

        system_commands = ["shutdown", "restart", "sleep"]
        if lower_text in system_commands:
            self._pending_command = lower_text
            self._set_state("IDLE")
            self._set_message(f"{lower_text.capitalize()} the PC? Confirm / Cancel")
            return

        if lower_text == "confirm" and self._pending_command:
            cmd = self._pending_command
            self._set_message(f"Executing {cmd}...")
            self._pending_command = None
            logger.info(f"MOCK {cmd.upper()} EXECUTED LCOALLY")
            self._set_state("TOOL_EXECUTION")
            await asyncio.sleep(2)
            self._set_state("IDLE")
            self._set_message(f"Mock {cmd} finished.")
            return

        if lower_text == "cancel" and self._pending_command:
            self._set_message("System command cancelled.")
            self._pending_command = None
            self._set_state("IDLE")
            return

        self._pending_command = None

        # Orchestrator run
        self._run_active = True
        self._run_uid = uid
        try:
            await self._orchestrator.run(text)
            self._update_memory_count()

            if not self._orchestrator.is_cancelled and uid == self._uid:
                for seg_text, nl in self._chunker.flush():
                    self._queue_segment(seg_text, nl)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            self._errored = True
            self._set_state("ERROR", str(e))
        finally:
            if self._run_uid == uid:
                self._run_active = False
            # Lets the audio engine report "utterance complete" once the last segment has been *heard*.
            self._voice_engine.end_utterance(uid)

    def handle_confirm(self, approved: bool):
        self._loop.call_soon_threadsafe(self._orchestrator.provide_confirmation, approved)

    def _update_memory_count(self):
        if self._window and self.is_loaded:
            try:
                from .orchestrator.memory import get_all_memories
                count = len(get_all_memories())
                self._emit("aonyx-memory", {"count": count})
            except Exception as e:
                logger.error(f"Failed to set memory count: {e}")
