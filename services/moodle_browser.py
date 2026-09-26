"""
Moodle browser automation — opens NCSU Moodle in the user's browser
and uses pyautogui to grab the page content from the active tab.
"""

import time
import webbrowser
import pyautogui

MOODLE_URL = "https://moodle-courses2527.wolfware.ncsu.edu/my/"


def open_moodle() -> None:
    """Open the Moodle dashboard in the user's default browser."""
    webbrowser.open(MOODLE_URL)


def grab_active_page() -> str:
    """
    Grab the HTML content of the currently active browser tab
    using system-level keyboard shortcuts.
    
    Assumes the user has already switched to the browser tab
    showing the Moodle dashboard.
    
    Sequence:
      1. Select All (Ctrl+A)
      2. Copy (Ctrl+C)
      3. Read from clipboard
    """
    # Small delay to let the system settle
    time.sleep(0.3)

    # Select all
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)

    # Copy
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)

    # Read clipboard
    html = _read_clipboard()
    return html


def _read_clipboard() -> str:
    """Read text from the system clipboard."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Hide the window
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception as e:
        raise RuntimeError(f"Could not read clipboard: {e}")


def switch_to_browser() -> None:
    """
    Alt+Tab to switch back to the browser.
    Only works if we know what was previously focused.
    """
    pyautogui.hotkey("alt", "tab")
    time.sleep(0.3)