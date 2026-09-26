"""
Moodle browser automation — navigates to assignment URLs and grabs
page content (instructions, Google Doc links, etc.) from the active tab.

Uses PyAutoGUI for keyboard simulation and pyperclip for clipboard.
"""

import time

try:
    import pyautogui
    import pyperclip
except ImportError:  # e.g. Intel Macs on Python 3.9, where pyobjc won't build
    pyautogui = None
    pyperclip = None


def _put_clipboard(text: str) -> None:
    """Put text into the system clipboard."""
    pyperclip.copy(text)


def _read_clipboard() -> str:
    """Read text from the system clipboard."""
    return pyperclip.paste()


def grab_moodle_page(url: str, load_wait: int = 5) -> str:
    """
    Opens a new browser tab, navigates to the given URL,
    waits for it to load, then copies the page content.

    Full sequence:
      1. Put URL in clipboard
      2. Ctrl+T       — open new tab
      3. Ctrl+V       — paste URL into address bar
      4. Enter        — navigate
      5. Wait N sec   — let the page load
      6. Escape x2    — clear address bar focus
      7. Ctrl+A       — select all
      8. Ctrl+C       — copy
      9. Ctrl+W       — close the tab
      10. Read clipboard → return
    """
    if pyautogui is None or pyperclip is None:
        raise RuntimeError("Auto-grab needs pyautogui and pyperclip, which aren't installed here. Use \"Advanced: paste HTML manually\" instead.")
    # 1. Copy URL to clipboard
    _put_clipboard(url)
    time.sleep(0.2)

    # 2. New tab
    pyautogui.hotkey("ctrl", "t")
    time.sleep(0.3)

    # 3. Paste URL
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)

    # 4. Navigate
    pyautogui.press("enter")
    time.sleep(1)

    # 5. Wait for page load
    time.sleep(load_wait)

    # 6. Escape x2 — clear address bar / popups
    pyautogui.press("escape")
    time.sleep(0.2)
    pyautogui.press("escape")
    time.sleep(0.2)

    # 7. Select all
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)

    # 8. Copy
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.5)

    # 9. Read clipboard (BEFORE closing tab)
    html = _read_clipboard()

    # 10. Close the tab
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.2)

    return html