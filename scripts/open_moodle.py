"""
Open NCSU Moodle dashboard in your default browser.

Usage:
    python scripts/open_moodle.py
"""

import webbrowser
import sys

# NCSU WolfWare Moodle dashboard URL
MOODLE_URL = "https://moodle-courses2527.wolfware.ncsu.edu/my/"

def open_moodle(url: str = MOODLE_URL) -> None:
    """Open the Moodle dashboard in the user's default browser."""
    print(f"🌐 Opening Moodle dashboard in your browser...")
    print(f"   {url}")
    print()
    print("   Once logged in, come back to the Dashboard Inspector")
    print("   and click 'Fetch Dashboard' to pull your assignments.")
    print()

    opened = webbrowser.open(url)

    if opened:
        print("✅ Browser opened successfully!")
    else:
        print("❌ Could not open browser automatically.")
        print(f"   Open this URL manually: {url}")
        sys.exit(1)


if __name__ == "__main__":
    open_moodle()