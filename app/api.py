import asyncio
import threading
import logging
import sys
import time
import re
from .llm import OllamaClient
from .voice import VoiceEngine
from .orchestrator.provider import OllamaProvider
from .orchestrator.engine import Orchestrator
from .orchestrator.registry import registry, ToolPermission

logger = logging.getLogger(__name__)

class DesktopAPI:
    def __init__(self):
        self._window = None
        self.is_loaded = False
        self._llm = OllamaClient(host="127.0.0.1", port=11434, model="llama3:latest")
        self._pending_command = None
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self._loop = asyncio.new_event_loop()
        
        self._provider = OllamaProvider()
        ui_callbacks = {
            "set_state": self._set_state,
            "show_tool_activity": self._show_tool_activity,
            "request_confirmation": self._request_confirmation,
            "stream_text": self._stream_text
        }
        self._orchestrator = Orchestrator(self._provider, ui_callbacks)
        
        self._voice_engine = VoiceEngine(self._on_voice_event)
        self.last_rms_time = 0
        
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

    def _set_state(self, state: str, errorText: str = ""):
        if self._window and self.is_loaded:
            try:
                self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-state", {{detail: {{state: "{state}"}}}}))')
                if state == "ERROR" and errorText:
                    self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-error", {{detail: {{errorText: "{errorText}"}}}}))')
            except Exception as e:
                logger.error(f"Failed to set state {state}: {e}")

    def _set_message(self, message: str):
        if self._window and self.is_loaded:
            # Escape newlines and quotes for JS evaluation
            escaped_msg = message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
            try:
                self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-message", {{detail: {{message: "{escaped_msg}"}}}}))')
            except Exception as e:
                logger.error(f"Failed to set message: {e}")

    def _show_tool_activity(self, tool_name: str, status: str):
        if self._window and self.is_loaded:
            escaped_name = tool_name.replace('"', '\\"')
            escaped_status = status.replace('"', '\\"')
            try:
                self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-tool", {{detail: {{name: "{escaped_name}", status: "{escaped_status}"}}}}))')
            except Exception:
                pass

    def _request_confirmation(self, tool_name: str, args: dict):
        if self._window and self.is_loaded:
            import json
            escaped_name = tool_name.replace('"', '\\"')
            escaped_args = json.dumps(args).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            try:
                self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-confirm", {{detail: {{name: "{escaped_name}", args: "{escaped_args}"}}}}))')
            except Exception:
                pass

    def _stream_text(self, chunk: str, full: str):
        import re
        
        # Match everything after `"response": "` up to the end of the string
        match = re.search(r'"response"\s*:\s*"(.*)', full, re.DOTALL)
        if not match:
            return
            
        clean_full = match.group(1)
        # Remove trailing unescaped quotes and braces
        clean_full = re.sub(r'(?<!\\)"\s*\}?\s*$', '', clean_full)
        # Unescape common JSON sequences
        clean_full = clean_full.replace('\\n', '\n').replace('\\"', '"')
        
        self._set_message(f"Aonyx: {clean_full}")
        
        if not hasattr(self, 'last_clean_len'):
            self.last_clean_len = 0
            
        new_text = clean_full[self.last_clean_len:]
        if not new_text:
            return
            
        self.last_clean_len = len(clean_full)
        
        if not hasattr(self, 'sentence_buffer'):
            self.sentence_buffer = ""
            
        self.sentence_buffer += new_text
        
        if any(punct in self.sentence_buffer for punct in ['.', '?', '!', '\n']):
            parts = re.split(r'([.?!\n])', self.sentence_buffer)
            self.sentence_buffer = parts.pop()
            complete_sentence = "".join(parts).strip()
            if complete_sentence:
                clean_text = re.sub(r'```.*?```', '', complete_sentence, flags=re.DOTALL)
                clean_text = re.sub(r'\*|_|`', '', clean_text)
                if clean_text:
                    logger.info(f"Queued for TTS (stream): {clean_text}")
                    self._voice_engine.speak(clean_text)

    def _on_voice_event(self, event_type, data):
        if event_type == "STATE":
            self._set_state(data)
        elif event_type == "RMS_UPDATE":
            # Throttle RMS updates to roughly 30Hz (0.033s)
            now = time.time()
            if now - self.last_rms_time > 0.033:
                self.last_rms_time = now
                if self._window and self.is_loaded:
                    try:
                        self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("whis-rms", {{detail: {{rms: {data}}}}}));')
                    except Exception:
                        pass
        elif event_type == "TRANSCRIPT":
            # Safely dispatch back to the asyncio loop
            self._loop.call_soon_threadsafe(self.send_message, data)
        elif event_type == "VOICE_READY":
            pass
        elif event_type == "VOICE_ERROR":
            self._set_state("ERROR", data)

    def toggle_listening(self):
        """Called from PTT hotkey or UI button"""
        if self._voice_engine.is_listening:
            self._voice_engine.stop_listening()
            self._voice_engine.process_audio()
        else:
            if self._voice_engine.start_listening():
                self._set_state("LISTENING")
                self._set_message("Listening...")

    # --- JS Accessible Methods ---
    def send_message(self, text: str):
        """Called from the frontend"""
        logger.info(f"Received message from UI: {text}")
        self._voice_engine.interrupt_tts()
        
        # Call orchestrator cancel in a thread-safe way
        self._loop.call_soon_threadsafe(self._orchestrator.cancel)
        
        self.sentence_buffer = ""
        self.last_clean_len = 0
        self._set_state("THINKING")
        self._set_message(f"User: {text}\n\nThinking...")
        
        asyncio.run_coroutine_threadsafe(self._process_message(text), self._loop)

    def retry_last(self, text: str):
        logger.info(f"Retrying message from UI: {text}")
        self._set_state("THINKING")
        self._set_message(f"User: {text}\n\nRetrying request...")
        asyncio.run_coroutine_threadsafe(self._process_message(text, is_retry=True), self._loop)

    async def _process_message(self, text: str, is_retry=False):
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
        
        # Add orchestrator logic
        try:
            await self._orchestrator.run(text)
            self._update_memory_count()
            
            if not self._orchestrator.is_cancelled:
                # Flush any remaining text in the sentence buffer
                if hasattr(self, 'sentence_buffer') and self.sentence_buffer.strip():
                    import re
                    clean_text = re.sub(r'\*|_|`', '', self.sentence_buffer.strip())
                    if clean_text:
                        logger.info(f"Queued for TTS (flush): {clean_text}")
                        self._voice_engine.speak(clean_text)
                    self.sentence_buffer = ""
                
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            self._set_state("ERROR", str(e))
            
    def handle_confirm(self, approved: bool):
        self._loop.call_soon_threadsafe(self._orchestrator.provide_confirmation, approved)

    def _update_memory_count(self):
        if self._window and self.is_loaded:
            try:
                from .orchestrator.memory import get_all_memories
                count = len(get_all_memories())
                self._window.evaluate_js(f'window.dispatchEvent(new CustomEvent("aonyx-memory", {{detail: {{count: {count}}}}}));')
            except Exception as e:
                logger.error(f"Failed to set memory count: {e}")

