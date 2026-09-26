"""
Moodle NCSU dashboard scraper.

Parses HTML from the NCSU Moodle (WolfWare) dashboard page and extracts
upcoming assignments with due dates, course names, and detail links.
Handles both the timeline block and the course overview table.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from utils.helpers import MOODLE_BASE_URL


# ── Types ──────────────────────────────────────────────────────────────

class MoodleAssignment:
    """A single assignment extracted from the Moodle dashboard."""

    def __init__(
        self,
        title: str,
        course: str = "",
        due_date: str = "",
        due_timestamp: Optional[int] = None,
        url: str = "",
        overdue: bool = False,
        description: str = "",
    ):
        self.title = title
        self.course = course
        self.due_date = due_date
        self.due_timestamp = due_timestamp  # unix seconds
        self.url = url
        self.overdue = overdue
        self.description = description

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "course": self.course,
            "due_date": self.due_date,
            "due_timestamp": self.due_timestamp,
            "url": self.url,
            "overdue": self.overdue,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return f"<MoodleAssignment '{self.title}' due={self.due_date}>"


# ── Helpers ─────────────────────────────────────────────────────────────

def _resolve_url(href: str) -> str:
    """Make relative Moodle URLs absolute."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    # Remove leading slash if present so urljoin works properly
    href = href.lstrip("/")
    return f"{MOODLE_BASE_URL.rstrip('/')}/{href}"


def _parse_timestamps(text: str) -> Optional[int]:
    """Try to extract a unix timestamp from a string (e.g. '1490320388')."""
    match = re.search(r"\b(1[5-9]\d{8,9})\b", text)  # 10-digit unix-ish
    if match:
        return int(match.group(1))
    return None


# ── Parsers (tried in priority order) ──────────────────────────────────

def _parse_timeline_block(soup: BeautifulSoup) -> list[MoodleAssignment]:
    """
    Parse the Moodle 4.x timeline block (data-region event list).

    Selectors (from Moodle 4.x source):
      - div[data-region="event-list-item"]   — each event
      - h6.event-name a                       — title + link
      - small                                  — description + course name
      - .badge.badge-danger                    — overdue indicator
    """
    assignments: list[MoodleAssignment] = []
    items = soup.select('div[data-region="event-list-item"]')

    for item in items:
        # Title + URL
        title_el = item.select_one("h6.event-name a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = _resolve_url(title_el.get("href", ""))

        # Overdue badge
        overdue = bool(item.select_one(".badge.badge-danger"))

        # Small.mb-0 — contains activity string and course name (middot-separated)
        info_small = item.select_one("small.mb-0")
        activity_str = ""
        course_name = ""
        if info_small:
            text = info_small.get_text(" ", strip=True)
            # Split on middot / bullet characters
            parts = re.split(r"\s*[·•]\s*", text)
            if parts:
                activity_str = parts[0].strip()
            if len(parts) > 1:
                course_name = parts[-1].strip()

        # Due time from the small.text-right element
        time_el = item.select_one("small.text-right")
        due_date = time_el.get_text(strip=True) if time_el else ""

        assignments.append(MoodleAssignment(
            title=title,
            course=course_name,
            due_date=due_date,
            url=url,
            overdue=overdue,
            description=activity_str,
        ))

    return assignments


def _parse_course_overview(soup: BeautifulSoup) -> list[MoodleAssignment]:
    """
    Fallback: parse the course overview block (common in older themes).

    Looks for cards with course names and assignment lists.
    """
    assignments: list[MoodleAssignment] = []

    # Look for course overview cards
    cards = soup.select('[data-region="course-events"], .card.dashboard-card')
    for card in cards:
        course_el = card.select_one(".card-header h3, .card-header h5, .card-title")
        course_name = course_el.get_text(strip=True) if course_el else ""

        # Find assignment-like links within the card
        for link in card.select("a[href*='assign'], a[href*='mod/assign']"):
            title = link.get_text(strip=True)
            if not title:
                continue
            url = _resolve_url(link.get("href", ""))
            assignments.append(MoodleAssignment(
                title=title,
                course=course_name,
                url=url,
            ))

    return assignments


def _parse_generic_table(soup: BeautifulSoup) -> list[MoodleAssignment]:
    """
    Fallback: scan tables with due-date-like text and assignment links.
    """
    assignments: list[MoodleAssignment] = []
    tables = soup.find_all("table")

    for table in tables:
        rows = table.select("tr")
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            # Look for assignment links
            link = row.select_one("a[href*='assign'], a[href*='mod/assign']")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = _resolve_url(link.get("href", ""))
            cell_text = " | ".join(c.get_text(strip=True) for c in cells)

            # Try to find a date-like string
            date_match = re.search(
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},? \d{4}",
                cell_text,
            )
            due_date = date_match.group(0) if date_match else ""

            assignments.append(MoodleAssignment(
                title=title,
                due_date=due_date,
                url=url,
            ))

    return assignments


def _parse_list_items(soup: BeautifulSoup) -> list[MoodleAssignment]:
    """
    Fallback: look for list items / li elements containing assignment links.
    """
    assignments: list[MoodleAssignment] = []
    for li in soup.select("li:has(a[href*='assign'])"):
        link = li.select_one("a[href*='assign']")
        title = link.get_text(strip=True) if link else ""
        url = _resolve_url(link.get("href", "")) if link else ""
        text = li.get_text(" ", strip=True)

        date_match = re.search(
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},? \d{4}",
            text,
        )
        due_date = date_match.group(0) if date_match else ""

        if title:
            assignments.append(MoodleAssignment(
                title=title,
                due_date=due_date,
                url=url,
            ))

    return assignments


# ── Public API ─────────────────────────────────────────────────────────

def parse_dashboard(html: str) -> list[dict]:
    """
    Parse Moodle dashboard HTML into a list of assignment dicts.

    Tries multiple parsing strategies in priority order:
      1. Timeline block (data-region event-list-item)
      2. Course overview cards
      3. Generic tables with assignment links
      4. List items with assignment links
    """
    soup = BeautifulSoup(html, "html.parser")

    # Priority 1: Timeline block (Moodle 4.x standard)
    assignments = _parse_timeline_block(soup)
    if assignments:
        return [a.to_dict() for a in assignments]

    # Priority 2: Course overview cards
    assignments = _parse_course_overview(soup)
    if assignments:
        return [a.to_dict() for a in assignments]

    # Priority 3: Generic tables
    assignments = _parse_generic_table(soup)
    if assignments:
        return [a.to_dict() for a in assignments]

    # Priority 4: List items
    assignments = _parse_list_items(soup)
    if assignments:
        return [a.to_dict() for a in assignments]

    return []


def extract_assignment_detail(html: str) -> dict:
    """
    Parse an individual assignment page to extract description and metadata.

    Called when we fetch each assignment's detail page (future enhancement).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Moodle assignment description is usually in .no-overflow or #intro
    desc_el = soup.select_one(".no-overflow, #intro, [data-region='assignment-info']")
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Due date from the assignment info section
    date_el = soup.select_one(
        "[data-region='activity-dates'], .assign-due-date, "
        "dt:contains('Due') + dd, th:contains('Due') + td"
    )
    due_date = date_el.get_text(strip=True) if date_el else ""

    return {
        "description": description,
        "due_date": due_date,
    }