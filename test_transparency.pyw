import webview
import os
import sys

def on_loaded():
    print("Window loaded successfully.")
    # We will let it run for 10 seconds then close so the agent knows it worked.
    import time
    time.sleep(10)
    window.destroy()

html_path = 'file:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_transparency.html').replace('\\\\', '/')

window = webview.create_window(
    'Transparency Spike',
    html_path,
    frameless=True,
    transparent=True,
    on_top=True,
    width=600,
    height=600
)

window.events.loaded += on_loaded
webview.start()
