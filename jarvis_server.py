import os
import sys
import time
import psutil
import asyncio
import logging
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from executors.ollama import generate_response
from ui.voice_trigger import VoiceTrigger
from ui.tts import TextToSpeech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount the static directory
app.mount("/web", StaticFiles(directory="web"), name="web")

# SYSTEM_PROMPT removed. Moved to knowledge_base.txt

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()
tts = TextToSpeech()
event_loop = asyncio.new_event_loop()

def broadcast_sync(message: dict):
    # Helper to broadcast from sync threads
    asyncio.run_coroutine_threadsafe(manager.broadcast(message), event_loop)

is_sleeping = False
is_processing = False
cancel_flag = False
is_locked = True

class JarvisController:
    def __init__(self):
        self.voice_trigger = VoiceTrigger(
            on_wake_callback=self._on_wake,
            on_command_callback=self._on_command,
            on_error_callback=self._on_error,
        )

    def _on_wake(self, text=""):
        global is_sleeping
        logger.info(f"Wake word detected! Text: {text}")
        
        if is_sleeping:
            wake_phrases = ["wake up", "turn on", "power on", "online"]
            if any(phrase in text.lower() for phrase in wake_phrases):
                # Direct wake up command detected by SAPI!
                is_sleeping = False
                broadcast_sync({"type": "action", "action": "POWER_ON"})
                tts.speak("Systems back online. Awaiting your command, sir.", on_done_callback=self.voice_trigger.resume)
                return
                
            # Silently listen for the wake up command without UI/TTS
            self.voice_trigger.listen_for_command()
            return

        import random
        broadcast_sync({"type": "state", "state": "listening"})
        
        responses = [
            "Online and ready.",
            "Listening.",
            "Awaiting input.",
            "System active.",
            "I am here."
        ]
        chosen_response = random.choice(responses)
        
        broadcast_sync({"type": "transcript", "text": chosen_response})
        
        def start_listening():
            self.voice_trigger.listen_for_command()
            
        tts.speak(chosen_response, on_done_callback=start_listening)

    def _on_command(self, command: str):
        global is_sleeping, is_processing, cancel_flag
        
        logger.info(f"Command: {command}")
        
        # Ignore empty commands and common Whisper hallucinations
        ignore_list = ["thank you.", "thank you", "okay.", "okay", "subscribe.", "thanks for watching.", "you.", "i.", "follow.", "follow"]
        if not command.strip() or command.strip().lower() in ignore_list:
            broadcast_sync({"type": "state", "state": "idle"})
            broadcast_sync({"type": "transcript", "text": "Waiting for command..."})
            self.voice_trigger.resume()
            return

        cmd_lower = command.lower().strip()
        
        if is_sleeping:
            if "turn on" in cmd_lower or "wake up" in cmd_lower or "power on" in cmd_lower:
                is_sleeping = False
                broadcast_sync({"type": "action", "action": "POWER_ON"})
                tts.speak("Systems back online. Awaiting your command, sir.", on_done_callback=self.voice_trigger.resume)
            else:
                self.voice_trigger.resume()
            return
            
        if "shut down" in cmd_lower or "shutdown" in cmd_lower or "sleep" in cmd_lower or "turn off" in cmd_lower:
            is_sleeping = True
            broadcast_sync({"type": "action", "action": "POWER_OFF"})
            tts.speak("Shutting down core systems. Goodbye, sir.", on_done_callback=self.voice_trigger.resume)
            return

        if is_processing:
            logger.info("Ignoring command because system is processing.")
            return

        is_processing = True
        cancel_flag = False

        broadcast_sync({"type": "state", "state": "thinking"})
        broadcast_sync({"type": "transcript", "text": command})

        def ask_ollama():
            global is_processing, cancel_flag, is_locked
            import datetime
            import re
            import urllib.parse
            
            cmd_lower = command.lower().strip()
            
            if "lock system" in cmd_lower or "lock the system" in cmd_lower:
                is_locked = True
                response = "System locked. Face authentication required to proceed."
                broadcast_sync({"type": "state", "state": "speaking"})
                broadcast_sync({"type": "response", "text": response, "user_text": command})
                
                def on_speak_done_face():
                    global is_processing
                    is_processing = False
                    broadcast_sync({"type": "state", "state": "idle"})
                    self.voice_trigger.resume()
                
                tts.speak(response, on_done_callback=on_speak_done_face)
                return

            if "register my face" in cmd_lower or "scan my face" in cmd_lower or "who am i" in cmd_lower:
                from ui.face_scan import FaceScanner
                scanner = FaceScanner()
                if "register my face" in cmd_lower:
                    response = scanner.register_creator()
                else:
                    response = scanner.verify_creator()
                    if "Identity verified" in response:
                        is_locked = False
                        response += " System unlocked."
                    
                broadcast_sync({"type": "state", "state": "speaking"})
                broadcast_sync({"type": "response", "text": response, "user_text": command})
                
                def on_speak_done_face():
                    global is_processing
                    is_processing = False
                    broadcast_sync({"type": "state", "state": "idle"})
                    self.voice_trigger.resume()
                
                if cancel_flag:
                    on_speak_done_face()
                    return
                    
                tts.speak(response, on_done_callback=on_speak_done_face)
                return
                
            if is_locked:
                response = "System locked. Please scan your face to authenticate."
                broadcast_sync({"type": "state", "state": "speaking"})
                broadcast_sync({"type": "response", "text": response, "user_text": command})
                
                def on_speak_done_locked():
                    global is_processing
                    is_processing = False
                    broadcast_sync({"type": "state", "state": "idle"})
                    self.voice_trigger.resume()
                
                tts.speak(response, on_done_callback=on_speak_done_locked)
                return

            now = datetime.datetime.now().strftime("%I:%M %p on %A, %B %d, %Y")
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            # Read reminders
            reminders_text = "No active reminders."
            try:
                with open("reminders.txt", "r") as f:
                    content = f.read().strip()
                    if content: reminders_text = content
            except Exception:
                pass
            
            # Read knowledge base
            kb_text = "Knowledge base missing."
            try:
                with open("knowledge_base.txt", "r") as f:
                    kb_text = f.read().strip()
            except Exception:
                pass
            
            dynamic_prompt = (
                f"{kb_text}\n\n"
                f"--- CURRENT CONTEXT ---\n"
                f"Time & Date: {now}\n"
                f"System CPU: {cpu}%, RAM: {mem}%\n"
                f"Active Reminders:\n{reminders_text}"
            )
            
            prompt = f"{dynamic_prompt}\nUser: {command}\nW.H.I.S.:"
            try:
                # Use a new loop for Ollama if running sync, or just run_until_complete
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(generate_response(prompt))
                loop.close()
            except Exception as e:
                response = f"Apologies Sir, I encountered an error: {e}"
                logger.error(f"Ollama error: {e}")

            if cancel_flag:
                logger.info("Process cancelled before execution.")
                is_processing = False
                broadcast_sync({"type": "state", "state": "idle"})
                broadcast_sync({"type": "transcript", "text": "Process Cancelled."})
                self.voice_trigger.resume()
                return

            # Fallback Intent Matcher in case LLM forgets the tag
            cmd_lower = command.lower().strip()
            if ("open youtube" in cmd_lower or cmd_lower == "youtube" or cmd_lower == "youtube.") and "ACTION:" not in response.upper():
                response += "\n[ACTION: OPEN_BROWSER youtube.com]"
            elif ("open google chrome" in cmd_lower or "open chrome" in cmd_lower or cmd_lower == "chrome" or cmd_lower == "google chrome") and "ACTION:" not in response.upper():
                response += "\n[ACTION: OPEN_APP chrome]"
            elif ("open notepad" in cmd_lower or cmd_lower == "notepad") and "ACTION:" not in response.upper():
                response += "\n[ACTION: OPEN_APP notepad]"
            elif "volume up" in cmd_lower and "ACTION:" not in response.upper():
                response += "\n[ACTION: VOLUME_UP]"
            elif "volume down" in cmd_lower and "ACTION:" not in response.upper():
                response += "\n[ACTION: VOLUME_DOWN]"
            elif "mute" in cmd_lower and "ACTION:" not in response.upper():
                response += "\n[ACTION: VOLUME_MUTE]"

            # Intercept Actions
            action_match = re.search(r'ACTION:\s*(.+?)(?:\]|$|\n)', response, flags=re.IGNORECASE)
            if action_match:
                action_str = action_match.group(1).replace("[", "").replace("]", "").strip()
                logger.info(f"Executing Action: {action_str}")
                action_upper = action_str.upper()
                try:
                    if action_upper.startswith("OPEN_BROWSER"):
                        url = action_str[12:].strip()
                        if not url.startswith("http"): url = "https://" + url
                        broadcast_sync({"type": "action", "action": "OPEN_BROWSER", "url": url})
                    elif action_upper.startswith("OPEN_APP"):
                        app_name = action_str[8:].strip().lower()
                        # Use hidden powershell to avoid Windows 'ding' error sound if app isn't found
                        os.system(f'powershell -WindowStyle Hidden -Command "Start-Process {app_name} -ErrorAction SilentlyContinue"')
                    elif action_upper.startswith("SEARCH"):
                        query = action_str[6:].strip()
                        broadcast_sync({"type": "action", "action": "SEARCH", "query": query})
                    elif action_upper.startswith("PLAY_MUSIC"):
                        song = action_str[10:].strip()
                        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(song)
                        broadcast_sync({"type": "action", "action": "OPEN_BROWSER", "url": url})
                    elif action_upper.startswith("VOLUME_UP"):
                        os.system('powershell -c "(new-object -com wscript.shell).SendKeys([char]175)"')
                    elif action_upper.startswith("VOLUME_DOWN"):
                        os.system('powershell -c "(new-object -com wscript.shell).SendKeys([char]174)"')
                    elif action_upper.startswith("VOLUME_MUTE"):
                        os.system('powershell -c "(new-object -com wscript.shell).SendKeys([char]173)"')
                    elif action_upper.startswith("REMIND"):
                        reminder_text = action_str[6:].strip()
                        if reminder_text:
                            with open("reminders.txt", "a") as f:
                                f.write(f"- {reminder_text}\n")
                    elif action_upper.startswith("LEARN"):
                        fact_text = action_str[5:].strip()
                        if fact_text:
                            with open("knowledge_base.txt", "a") as f:
                                f.write(f"\n- {fact_text}")
                    elif action_upper.startswith("READ_REMINDERS"):
                        pass # The LLM naturally reads them from context
                except Exception as e:
                    logger.error(f"Action execution failed: {e}")
                
                # Remove the tag from the spoken response
                response = re.sub(r'\[?ACTION:\s*.+?(?:\]|$|\n)', '', response, flags=re.IGNORECASE).strip()

            broadcast_sync({"type": "state", "state": "speaking"})
            broadcast_sync({"type": "response", "text": response, "user_text": command})

            def on_speak_done():
                global is_processing
                is_processing = False
                broadcast_sync({"type": "state", "state": "idle"})
                self.voice_trigger.resume()

            if cancel_flag:
                on_speak_done()
                return

            tts.speak(response, on_done_callback=on_speak_done)

        threading.Thread(target=ask_ollama, daemon=True).start()

    def _on_error(self, error: str):
        logger.error(f"Voice error: {error}")

    def start(self):
        self.voice_trigger.start()

jarvis_controller = JarvisController()

@app.on_event("startup")
async def startup_event():
    # Set the event loop globally for sync threads to access
    global event_loop
    event_loop = asyncio.get_running_loop()
    
    # Start Voice Trigger in background
    jarvis_controller.start()
    
    # Start Stats Emitter
    async def stats_emitter():
        while True:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('C:\\')
            stats = {
                "cpu": cpu,
                "ram_used": mem.used / (1024**3),
                "ram_total": mem.total / (1024**3),
                "ram_pct": mem.percent,
                "disk_free": disk.free / (1024**3),
                "disk_pct": disk.percent
            }
            await manager.broadcast({"type": "stats", "stats": stats})
            await asyncio.sleep(2)

    asyncio.create_task(stats_emitter())

@app.get("/")
async def get():
    with open("web/index.html", "r") as f:
        html = f.read()
    return HTMLResponse(html)

@app.get("/orb")
async def get_orb():
    with open("web/orb.html", "r") as f:
        html = f.read()
    return HTMLResponse(html)

@app.post("/api/wake")
async def api_wake():
    jarvis_controller._on_wake()
    return {"status": "ok"}

from fastapi import Request
@app.post("/api/chat")
async def api_chat(request: Request):
    data = await request.json()
    command = data.get("command", "")
    if command:
        # Run in background to avoid blocking the API
        import threading
        threading.Thread(target=jarvis_controller._on_command, args=(command,), daemon=True).start()
    return {"status": "ok"}

@app.post("/api/shutdown")
async def api_shutdown():
    global is_sleeping
    is_sleeping = True
    await manager.broadcast({"type": "action", "action": "POWER_OFF"})
    return {"status": "sleeping"}

@app.post("/api/cancel")
async def api_cancel():
    global cancel_flag, is_processing
    cancel_flag = True
    tts.stop()
    if not is_processing:
        await manager.broadcast({"type": "state", "state": "idle"})
        jarvis_controller.voice_trigger.resume()
    return {"status": "cancelled"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client right now, but we need to keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 to allow access from local network if desired, or 127.0.0.0
    logger.info("Starting JARVIS Web Server...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
