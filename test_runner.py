import webview
import threading
import time
from PIL import ImageGrab
import sys
import os

class Api:
    def __init__(self, mode_name):
        self.mode_name = mode_name
        
    def log_error(self, msg):
        print(f"[{self.mode_name} JS ERROR] {msg}")

    def log_msg(self, msg):
        print(f"[{self.mode_name} JS LOG] {msg}")

def run_test(mode_name, transparent, url_or_path, http_server=False):
    print(f"\n--- Starting Test: {mode_name} ---")
    api = Api(mode_name)
    
    window = webview.create_window(
        mode_name, 
        url_or_path,
        frameless=True, 
        transparent=transparent,
        on_top=True,
        width=800, 
        height=600,
        js_api=api
    )
    
    def on_loaded():
        print(f"[{mode_name}] Window loaded.")
        # Inject JS to catch errors
        window.evaluate_js('''
            window.onerror = function(msg, url, line) {
                if(window.pywebview && window.pywebview.api) {
                    window.pywebview.api.log_error(msg + ' at ' + line);
                }
            };
            var oldLog = console.log;
            console.log = function() {
                var msg = Array.from(arguments).join(' ');
                oldLog.apply(console, arguments);
                if(window.pywebview && window.pywebview.api) {
                    window.pywebview.api.log_msg(msg);
                }
            };
            var oldError = console.error;
            console.error = function() {
                var msg = Array.from(arguments).join(' ');
                oldError.apply(console, arguments);
                if(window.pywebview && window.pywebview.api) {
                    window.pywebview.api.log_error(msg);
                }
            };
        ''')
        
        # Wait a bit for rendering
        time.sleep(3)
        
        # Take screenshot
        print(f"[{mode_name}] Test completed successfully.")
        
        window.destroy()

    window.events.loaded += on_loaded
    webview.start(http_server=http_server, debug=True)

html_path = 'file:///' + os.path.abspath('test_transparency.html').replace('\\', '/')
html_path_local = 'test_transparency.html'

# Test 1a: http_server=True, transparent=True
run_test("spike_http_trans", True, html_path_local, http_server=True)

# Test 1b: http_server=True, transparent=False
run_test("spike_http_opaque", False, html_path_local, http_server=True)

# Test 1c: file:// protocol, transparent=True
run_test("spike_file_trans", True, html_path, http_server=False)
