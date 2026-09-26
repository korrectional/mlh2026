"""Moodle NCSU dashboard scraper — stub for the Dashboard Inspector branch."""

from bs4 import BeautifulSoup

def parse_dashboard(html: str) -> list[dict]:
    """Parse Moodle dashboard HTML into a list of assignments."""
    # TODO: branch will implement NCSU Moodle DOM selectors
    soup = BeautifulSoup(html, "html.parser")
    return [
        {"title": "Stub Assignment", "due": "Soon", "url": ""}
    ]