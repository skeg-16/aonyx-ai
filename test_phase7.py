import sys
import os

# Add to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.orchestrator.desktop_tools import get_active_window, get_desktop_info, check_application, focus_application

def test_active_window():
    print("Testing get_active_window:")
    res = get_active_window({})
    print(res)

def test_desktop_info():
    print("Testing get_desktop_info:")
    res = get_desktop_info({})
    print(res)

def test_check_app():
    print("Testing check_application for 'notepad':")
    res = check_application({"app_name": "notepad"})
    print(res)
    print("Testing check_application for 'calculator':")
    res = check_application({"app_name": "calculator"})
    print(res)
    print("Testing check_application for 'nonexistent':")
    res = check_application({"app_name": "nonexistent"})
    print(res)

def test_focus():
    print("Testing focus_application for 'notepad':")
    res = focus_application({"app_name": "notepad"})
    print(res)

if __name__ == "__main__":
    test_active_window()
    test_desktop_info()
    test_check_app()
    test_focus()
