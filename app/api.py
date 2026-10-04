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

logger = logging.getLogger(__name__)

class DesktopAPI:
    def __init__(self):
        self._window = None
        self.is_loaded = False
        self.llm = OllamaClient(host="127.0.0.1", port=11434, model="llama3:latest")
        self.pending_command = None
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self.loop = asyncio.new_event_loop()
        
        self.provider = OllamaProvider()
        ui_callbacks = {
            "set_state": self._set_state,
            "show_tool_activity": self._show_tool_activity,
            "request_confirmation": self._request_confirmation,
            "stream_text": self._stream_text
        }
        self.orchestrator = Orchestrator(self.provider, ui_callbacks)
        
        self.voice_engine = VoiceEngine(self._on_voice_event)
        self.last_rms_time = 0
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def set_window(self, window):
        self._window = window

    def on_loaded(self):
        self.is_loaded = True
        logger.info("Window loaded. Running init check.")
        asyncio.run_coroutine_threadsafe(self._init_check(), self.loop)

    async def _init_check(self):
        is_healthy = await self.provider.health_check()
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
                    self.voice_engine.speak(clean_text)

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
            self.loop.call_soon_threadsafe(self.send_message, data)
        elif event_type == "VOICE_READY":
            pass
        elif event_type == "VOICE_ERROR":
            self._set_state("ERROR", data)

    def toggle_listening(self):
        """Called from PTT hotkey or UI button"""
        if self.voice_engine.is_listening:
            self.voice_engine.stop_listening()
            self.voice_engine.process_audio()
        else:
            if self.voice_engine.start_listening():
                self._set_state("LISTENING")
                self._set_message("Listening...")

    # --- JS Accessible Methods ---
    def send_message(self, text: str):
        """Called from the frontend"""
        logger.info(f"Received message from UI: {text}")
        self.voice_engine.interrupt_tts()
        
        # Call orchestrator cancel in a thread-safe way
        self.loop.call_soon_threadsafe(self.orchestrator.cancel)
        
        self.sentence_buffer = ""
        self.last_clean_len = 0
        self._set_state("THINKING")
        self._set_message(f"User: {text}\n\nThinking...")
        
        asyncio.run_coroutine_threadsafe(self._process_message(text), self.loop)

    def retry_last(self, text: str):
        logger.info(f"Retrying message from UI: {text}")
        self._set_state("THINKING")
        self._set_message(f"User: {text}\n\nRetrying request...")
        asyncio.run_coroutine_threadsafe(self._process_message(text, is_retry=True), self.loop)

    async def _process_message(self, text: str, is_retry=False):
        lower_text = text.strip().lower()
        
        # System Commands Routing
        if lower_text == "/listen":
            self.toggle_listening()
            return

        system_commands = ["shutdown", "restart", "sleep"]
        if lower_text in system_commands:
            self.pending_command = lower_text
            self._set_state("IDLE")
            self._set_message(f"{lower_text.capitalize()} the PC? Confirm / Cancel")
            return
            
        if lower_text == "confirm" and self.pending_command:
            cmd = self.pending_command
            self._set_message(f"Executing {cmd}...")
            self.pending_command = None
            logger.info(f"MOCK {cmd.upper()} EXECUTED LCOALLY")
            self._set_state("TOOL_EXECUTION")
            await asyncio.sleep(2)
            self._set_state("IDLE")
            self._set_message(f"Mock {cmd} finished.")
            return
            
        if lower_text == "cancel" and self.pending_command:
            self._set_message("System command cancelled.")
            self.pending_command = None
            self._set_state("IDLE")
            return

        self.pending_command = None
        
        # Add orchestrator logic
        try:
            await self.orchestrator.run(text)
            
            if not self.orchestrator.is_cancelled:
                # Flush any remaining text in the sentence buffer
                if hasattr(self, 'sentence_buffer') and self.sentence_buffer.strip():
                    import re
                    clean_text = re.sub(r'\*|_|`', '', self.sentence_buffer.strip())
                    if clean_text:
                        logger.info(f"Queued for TTS (flush): {clean_text}")
                        self.voice_engine.speak(clean_text)
                    self.sentence_buffer = ""
                
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            self._set_state("ERROR", str(e))
            
    def handle_confirm(self, approved: bool):
        self.loop.call_soon_threadsafe(self.orchestrator.provide_confirmation, approved)

