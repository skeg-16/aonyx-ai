import webview
import os
import asyncio
import threading
import logging
import keyboard
import pystray
from PIL import Image, ImageDraw
from executors.ollama import generate_response
from ui.voice_trigger import VoiceTrigger
from ui.tts import TextToSpeech

logging.getLogger('pywebview').setLevel(logging.CRITICAL)

def create_tray_image():
    # Generate a simple 64x64 blue circle for the tray icon
    image = Image.new('RGBA', (64, 64), (255, 255, 255, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill=(0, 150, 255))
    return image

class Api:
    def __init__(self):
        self.tts = TextToSpeech()
        self.window = None
        self.is_fullscreen = False
        self.is_visible = False
        
        self.voice_trigger = VoiceTrigger(
            on_wake_callback=self._on_wake,
            on_command_callback=self._on_command,
            on_error_callback=self._on_error
        )
        self.system_prompt = (
            "You are W.H.I.S., an advanced AI assistant. "
            "The user's name is Kieffer. "
            "Respond concisely and intelligently in English."
        )

    def get_system_stats(self):
        from ui.diagnostics import get_system_stats
        return get_system_stats()

    def set_window(self, window):
        self.window = window
        self.voice_trigger.start()

    def toggle_visibility(self):
        if not self.window: return
        if self.is_fullscreen:
            self.shrink_orb()
        else:
            self.expand_hud()

    def show_whis(self):
        if self.window:
            self.window.show()
            
    def hide_whis(self):
        if self.window:
            self.shrink_orb()

    def trigger_wake(self):
        self._on_wake()

    def expand_hud(self):
        if self.window and not self.is_fullscreen:
            self.is_fullscreen = True
            self.window.toggle_fullscreen()
            self.window.evaluate_js("document.body.classList.remove('mode-orb')")

    def shrink_orb(self):
        if self.window and self.is_fullscreen:
            self.is_fullscreen = False
            self.window.toggle_fullscreen()
            self.window.resize(300, 300)
            self.window.evaluate_js("document.body.classList.add('mode-orb')")

    def move_window(self, x, y):
        if self.window:
            try:
                self.window.move(int(x), int(y))
            except Exception:
                pass

    def _update_ui_state(self, state, text=''):
        if self.window:
            safe_text = text.replace(chr(39), chr(92) + chr(39)).replace(chr(10), ' ')
            js_code = 'window.updateJarvisState(' + chr(39) + state + chr(39) + ', ' + chr(39) + safe_text + chr(39) + ')'
            self.window.evaluate_js(js_code)

    def _on_wake(self, text=''):
        import random
        self.show_whis()
        self._update_ui_state('listening', 'Yes, Kieffer?')
        responses = [
            'Online, Kieffer.',
            'Awaiting input.',
            'Ready when you are.',
            'System active.',
            'I am listening.'
        ]
        
        def on_intro_done():
            self.voice_trigger.listen_for_command()
            
        self.tts.speak(random.choice(responses), on_done_callback=on_intro_done)

    def _on_command(self, command):
        if not command.strip():
            self._update_ui_state('idle', 'Waiting for command...')
            self.voice_trigger.resume()
            return

        self._update_ui_state('thinking', command)
        
        def ask_ollama():
            prompt = self.system_prompt + '\n\nKieffer: ' + command + '\nW.H.I.S.:'
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(generate_response(prompt))
                loop.close()
            except Exception as e:
                response = 'Error: ' + str(e)
            
            if self.window:
                safe_response = response.replace(chr(39), chr(92) + chr(39)).replace(chr(10), ' ')
                js_code = 'window.appendAiResponse(' + chr(39) + safe_response + chr(39) + ')'
                self.window.evaluate_js(js_code)
            
            self._update_ui_state('speaking', response)
            
            def on_speak_done():
                self._update_ui_state('idle', 'Awaiting input or voice command...')
                self.voice_trigger.resume()
                
            self.tts.speak(response, on_done_callback=on_speak_done)

        threading.Thread(target=ask_ollama, daemon=True).start()

    def _on_error(self, error):
        pass

    def process_text_command(self, command):
        self._on_command(command)
        return 'Command received'

    def quit_app(self, icon=None):
        if icon:
            icon.stop()
        if self.window:
            self.window.destroy()
        os._exit(0)

api = Api()

def setup_hotkey():
    keyboard.add_hotkey('ctrl+shift+space', api.toggle_visibility)

def setup_tray_icon():
    image = create_tray_image()
    menu = pystray.Menu(
        pystray.MenuItem('Show W.H.I.S.', lambda: api.show_whis()),
        pystray.MenuItem('Hide', lambda: api.hide_whis()),
        pystray.MenuItem('Quit', lambda icon, item: api.quit_app(icon))
    )
    icon = pystray.Icon("WHIS", image, "W.H.I.S. AI", menu)
    icon.run()

if __name__ == '__main__':
    html_path = 'file:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html').replace('\\\\', '/')
    window = webview.create_window(
        'W.H.I.S.', 
        html_path, 
        frameless=True, 
        transparent=True, 
        easy_drag=True,
        on_top=True,
        js_api=api, 
        width=300, 
        height=300,
        hidden=False
    )
    api.set_window(window)
    
    setup_hotkey()
    
    tray_thread = threading.Thread(target=setup_tray_icon, daemon=True)
    tray_thread.start()
    
    webview.start()
