"""
Moodle browser automation — navigates to assignment URLs and grabs
page content (instructions, Google Doc links, etc.) from the active tab.

Uses PyAutoGUI for keyboard simulation and pyperclip for clipboard.
"""

import time
import pyautogui
import pyperclip


def _put_clipboard(text: str) -> None:
    """Put text into the system clipboard."""
    pyperclip.copy(text)


def _read_clipboard() -> str:
    """Read text from the system clipboard."""
    return pyperclip.paste()


def grab_active_page() -> str:
    """
    Ctrl+A → Ctrl+C to copy the entire current page, read clipboard, return.
    No Escape, no navigation — just selects all and copies.
    """
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.4)
    return _read_clipboard()


def _grab_current_page() -> str:
    """
    Alias kept for internal use. Same as grab_active_page().
    """
    return grab_active_page()


# ── One-off: open a page, grab it, close the tab ──────────────────────

def grab_moodle_page(url: str, load_wait: int = 5) -> str:
    """
    Opens a new tab, navigates to the URL, grabs content, closes the tab.
    Used by the one-off "Grab Instructions" button.
    Does NOT keep the tab open.
    """
    _put_clipboard(url)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "t")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1)
    time.sleep(load_wait)
    html = _grab_current_page()
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.2)
    return html


# ── Open dashboard (keep it open) ──────────────────────────────────────

def open_dashboard_and_grab(url: str, load_wait: int = 2) -> str:
    """
    Open the Moodle dashboard in a new browser tab, wait for it to load,
    grab the page content via Ctrl+A → Ctrl+C.

    Crucially: does NOT close the tab. The dashboard tab stays open so
    we can Tab-navigate into individual assignments afterward.
    """
    _put_clipboard(url)
    time.sleep(0.1)

    pyautogui.hotkey("ctrl", "t")
    time.sleep(0.15)

    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)

    pyautogui.press("enter")
    time.sleep(0.3)
    time.sleep(load_wait)

    html = _grab_current_page()
    print(f"  📄 Dashboard grabbed ({len(html)} chars) — tab kept open")
    return html


# ── Tab-navigation description grabber ─────────────────────────────────

_DEFAULT_TAB_FIRST = 22    # Tab presses to reach the first assignment link
_DEFAULT_TAB_NEXT = 2      # Tab presses to jump from one to the next


def grab_assignment_descriptions(
    assignments: list[dict],
    load_wait: int = 2,
    tab_first: int = _DEFAULT_TAB_FIRST,
    tab_next: int = _DEFAULT_TAB_NEXT,
) -> list[dict]:
    """
    The dashboard tab is already open in the browser (from
    open_dashboard_and_grab). Now Tab-navigate from that tab to each
    assignment link, Enter to open it, Ctrl+A → Ctrl+C to grab the page,
    Alt+Left to go back to the dashboard. Repeats for every assignment.

    Args:
        assignments: List of assignment dicts from parse_dashboard().
                     Each gets a `_page_html` key.
        load_wait: Seconds to wait for each assignment page to load.
        tab_first: Tab presses to reach the first assignment link.
        tab_next:  Tab presses between consecutive assignment links.

    Returns:
        Same list with `_page_html` populated for each assignment.
    """
    count = len(assignments)
    if count == 0:
        return assignments

    print(f"\n  ⌨️  Tab-navigating through {count} assignment(s)...")
    print(f"     Tab {tab_first}x to first, then Tab {tab_next}x between each\n")

    # ── Tab to the first assignment link ────────────────────────────────
    for _ in range(tab_first):
        pyautogui.press("tab")
        time.sleep(0.06)
    time.sleep(0.3)

    # ── Visit each assignment ──────────────────────────────────────────
    for i in range(count):
        title = assignments[i].get("title", f"assignment-{i}")[:60]

        print(f"     [{i+1}/{count}] {title} ...", end=" ", flush=True)

        # Enter to open the assignment
        pyautogui.press("enter")
        time.sleep(0.5)
        time.sleep(load_wait)

        # Ctrl+A → Ctrl+C to grab the full page
        html = _grab_current_page()
        assignments[i]["_page_html"] = html

        print(f"{len(html)} chars", flush=True)

        # Alt+Left to go back to the dashboard
        pyautogui.hotkey("alt", "left")
        time.sleep(0.3)
        time.sleep(max(load_wait - 1, 1))  # wait for dashboard to reload

        # Tab to the next assignment link
        if i < count - 1:
            for _ in range(tab_next):
                pyautogui.press("tab")
                time.sleep(0.05)
            time.sleep(0.2)

    print(f"\n  ✅ Done — grabbed {count} assignment page(s)")

    # Close the dashboard tab — we're done with it
    print("     Closing dashboard tab...")
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.2)
    print()
    return assignments