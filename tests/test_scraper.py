"""
Test harness for the Moodle scraper.

Run:  python -m tests.test_scraper
"""

import json
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.moodle_scraper import parse_dashboard, extract_assignment_detail


def test_timeline_block():
    """Test parsing the standard Moodle 4.x timeline block."""
    html = """<!DOCTYPE html>
<html><body>
<div data-region="event-list-container">
    <div data-region="event-list-content">
        <div data-region="event-list-wrapper">

            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                 data-region="event-list-item">
                <div class="d-flex flex-wrap pb-1">
                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                        <small class="text-right text-nowrap align-self-center ml-1">
                            2:30 PM
                        </small>
                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                            <img alt="Assignment" title="Assignment" src="http://example.com/icon" class="icon">
                        </div>
                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                            <div class="d-flex">
                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                    <a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=12345"
                                       title="Homework 3 - Data Structures">
                                        Homework 3 - Data Structures</a>
                                </h6>
                            </div>
                            <small class="mb-0">
                                Assignment is due · CSC 316 - Data Structures
                            </small>
                        </div>
                    </div>
                    <div class="d-flex timeline-action-button">
                        <h6 class="event-action">
                            <a class="list-group-item-action btn btn-outline-secondary btn-sm text-nowrap"
                               href="https://wolfware.ncsu.edu/mod/assign/view.php?id=12345">
                            Submit assignment
                            </a>
                        </h6>
                    </div>
                </div>
                <div class="pt-2 border-bottom"></div>
            </div>

            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                 data-region="event-list-item">
                <div class="d-flex flex-wrap pb-1">
                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                        <small class="text-right text-nowrap align-self-center ml-1">
                            11:59 PM
                        </small>
                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                            <img alt="Assignment" title="Assignment" src="http://example.com/icon" class="icon">
                        </div>
                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                            <div class="d-flex">
                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                    <span class="badge badge-pill badge-danger ml-1 float-right">Overdue</span>
                                    <a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=67890"
                                       title="Lab Report 4 - Chemical Reactions">
                                        Lab Report 4 - Chemical Reactions</a>
                                </h6>
                            </div>
                            <small class="mb-0">
                                Assignment is due · CH 101 - Chemistry
                            </small>
                        </div>
                    </div>
                </div>
                <div class="pt-2 border-bottom"></div>
            </div>

            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                 data-region="event-list-item">
                <div class="d-flex flex-wrap pb-1">
                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                        <small class="text-right text-nowrap align-self-center ml-1">
                            8:00 AM
                        </small>
                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                            <img alt="Quiz" title="Quiz" src="http://example.com/icon" class="icon">
                        </div>
                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                            <div class="d-flex">
                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                    <a href="https://wolfware.ncsu.edu/mod/quiz/view.php?id=11111"
                                       title="Quiz 7 - Linear Regression">
                                        Quiz 7 - Linear Regression</a>
                                </h6>
                            </div>
                            <small class="mb-0">
                                Quiz closes · ST 370 - Probability & Statistics
                            </small>
                        </div>
                    </div>
                </div>
                <div class="pt-2 border-bottom"></div>
            </div>

        </div>
    </div>
</div>
</body></html>"""

    results = parse_dashboard(html)
    assert len(results) == 3, f"Expected 3 assignments, got {len(results)}"
    assert results[0]["title"] == "Homework 3 - Data Structures"
    assert results[0]["course"] == "CSC 316 - Data Structures"
    assert results[0]["url"] == "https://wolfware.ncsu.edu/mod/assign/view.php?id=12345"
    assert not results[0]["overdue"]

    assert results[1]["title"] == "Lab Report 4 - Chemical Reactions"
    assert results[1]["course"] == "CH 101 - Chemistry"
    assert results[1]["overdue"]

    assert results[2]["title"] == "Quiz 7 - Linear Regression"
    assert results[2]["course"] == "ST 370 - Probability & Statistics"

    print("  ✅ test_timeline_block passed")
    return results


def test_course_overview_block():
    """Test parsing course overview cards (fallback)."""
    html = """<!DOCTYPE html>
<html><body>
<div class="card dashboard-card" data-region="course-events">
    <div class="card-header">
        <h5 class="card-title">CSC 316 - Data Structures</h5>
    </div>
    <div class="card-body">
        <ul>
            <li><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=1">Programming Assignment 5</a></li>
            <li><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=2">Homework 4 - Trees</a></li>
        </ul>
    </div>
</div>
<div class="card dashboard-card">
    <div class="card-header">
        <h5 class="card-title">CH 101 - Chemistry</h5>
    </div>
    <div class="card-body">
        <ul>
            <li><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=3">Lab Report 5</a></li>
        </ul>
    </div>
</div>
</body></html>"""

    results = parse_dashboard(html)
    # course overview should parse 3 assignments
    assert len(results) == 3, f"Expected 3 assignments from course overview, got {len(results)}"
    assert results[0]["course"] == "CSC 316 - Data Structures"
    assert results[0]["title"] == "Programming Assignment 5"

    print("  ✅ test_course_overview_block passed")
    return results


def test_generic_table():
    """Test parsing generic tables (fallback)."""
    html = """<!DOCTYPE html>
<html><body>
<table>
    <tr>
        <th>Assignment</th>
        <th>Due Date</th>
        <th>Course</th>
    </tr>
    <tr>
        <td><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=10">Final Project Report</a></td>
        <td>12/15/2026</td>
        <td>CSC 316</td>
    </tr>
    <tr>
        <td><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=11">Problem Set 8</a></td>
        <td>11/30/2026</td>
        <td>MA 242</td>
    </tr>
</table>
</body></html>"""

    results = parse_dashboard(html)
    assert len(results) == 2, f"Expected 2 from generic table, got {len(results)}"
    assert results[0]["title"] == "Final Project Report"
    assert results[0]["due_date"] == "12/15/2026"

    print("  ✅ test_generic_table passed")
    return results


def test_list_items():
    """Test parsing li elements as last resort."""
    html = """<!DOCTYPE html>
<html><body>
<ul>
    <li><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=20">Reading Response 3</a> — Due: Oct 15</li>
    <li><a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=21">Discussion Post 7</a> — Due: Oct 18</li>
</ul>
</body></html>"""

    results = parse_dashboard(html)
    assert len(results) == 2, f"Expected 2 from list items, got {len(results)}"
    assert results[0]["title"] == "Reading Response 3"

    print("  ✅ test_list_items passed")
    return results


def test_empty_html():
    """Test with completely unrelated HTML."""
    html = "<html><body><h1>Hello World</h1><p>No assignments here.</p></body></html>"
    results = parse_dashboard(html)
    assert len(results) == 0, f"Expected 0 for empty HTML, got {len(results)}"
    print("  ✅ test_empty_html passed")


def test_extract_assignment_detail():
    """Test parsing an individual assignment detail page."""
    html = """<!DOCTYPE html>
<html><body>
<div class="no-overflow">
    <p>Implement a binary search tree with insert, delete, and search operations.
    Submit a single .py file. Include unit tests.</p>
</div>
<div data-region="activity-dates">
    <dt>Due</dt>
    <dd>Friday, October 20, 2026, 11:59 PM</dd>
</div>
</body></html>"""

    result = extract_assignment_detail(html)
    assert "binary search tree" in result["description"]
    assert "October 20" in result["due_date"]

    print("  ✅ test_extract_assignment_detail passed")


def test_realistic_ncsu_moodle():
    """
    Full realistic NCSU Moodle dashboard section.
    Simulates what you'd actually see on the WolfWare dashboard.
    """
    html = """<!DOCTYPE html>
<html><body>
<div id="page">
    <div id="region-main">
        <div class="card">
            <div class="card-body">
                <h3>Timeline</h3>
                <div data-region="event-list-container">
                    <div data-region="event-list-content">
                        <div data-region="event-list-wrapper">

                            <!-- Assignment 1: Normal, due soon -->
                            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                                 data-region="event-list-item">
                                <div class="d-flex flex-wrap pb-1">
                                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                                        <small class="text-right text-nowrap align-self-center ml-1">11:59 PM</small>
                                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                                            <img alt="" src="http://example.com/icon" class="icon">
                                        </div>
                                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                                            <div class="d-flex">
                                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                                    <a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=1001"
                                                       title="Homework 6 - Sorting Algorithms">
                                                        Homework 6 - Sorting Algorithms</a>
                                                </h6>
                                            </div>
                                            <small class="mb-0">
                                                Assignment is due · CSC 333 - Theory of Computation
                                            </small>
                                        </div>
                                    </div>
                                </div>
                                <div class="pt-2 border-bottom"></div>
                            </div>

                            <!-- Assignment 2: Overdue -->
                            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                                 data-region="event-list-item">
                                <div class="d-flex flex-wrap pb-1">
                                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                                        <small class="text-right text-nowrap align-self-center ml-1">11:59 PM</small>
                                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                                            <img alt="" src="http://example.com/icon" class="icon">
                                        </div>
                                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                                            <div class="d-flex">
                                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                                    <span class="badge badge-pill badge-danger">Overdue</span>
                                                    <a href="https://wolfware.ncsu.edu/mod/assign/view.php?id=1002"
                                                       title="Project 2 - Compiler Design">
                                                        Project 2 - Compiler Design</a>
                                                </h6>
                                            </div>
                                            <small class="mb-0">
                                                Assignment is due · CSC 444 - Compiler Design
                                            </small>
                                        </div>
                                    </div>
                                </div>
                                <div class="pt-2 border-bottom"></div>
                            </div>

                            <!-- Assignment 3: Quiz -->
                            <div class="list-group-item timeline-event-list-item flex-column pt-2 pb-0 border-0 px-2"
                                 data-region="event-list-item">
                                <div class="d-flex flex-wrap pb-1">
                                    <div class="d-flex mr-auto pb-1 mw-100 timeline-name">
                                        <small class="text-right text-nowrap align-self-center ml-1">8:00 AM</small>
                                        <div class="activityiconcontainer small assessment courseicon align-self-top align-self-center mx-3 mb-1 mb-sm-0 text-nowrap">
                                            <img alt="" src="http://example.com/icon" class="icon">
                                        </div>
                                        <div class="event-name-container flex-grow-1 line-height-3 nowrap text-truncate">
                                            <div class="d-flex">
                                                <h6 class="event-name mb-0 pb-1 text-truncate">
                                                    <a href="https://wolfware.ncsu.edu/mod/quiz/view.php?id=1003"
                                                       title="Quiz 3 - Finite Automata">
                                                        Quiz 3 - Finite Automata</a>
                                                </h6>
                                            </div>
                                            <small class="mb-0">
                                                Quiz closes · CSC 333 - Theory of Computation
                                            </small>
                                        </div>
                                    </div>
                                </div>
                                <div class="pt-2 border-bottom"></div>
                            </div>

                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
</body></html>"""

    results = parse_dashboard(html)
    assert len(results) == 3, f"Expected 3, got {len(results)}"

    # Check sorting puts overdue first
    # (sorted by router, not by parse_dashboard - but let's verify fields)
    assert results[0]["title"] == "Homework 6 - Sorting Algorithms"
    assert results[0]["course"] == "CSC 333 - Theory of Computation"
    assert results[0]["url"] == "https://wolfware.ncsu.edu/mod/assign/view.php?id=1001"
    assert results[0]["overdue"] == False

    assert results[1]["overdue"] == True
    assert results[1]["title"] == "Project 2 - Compiler Design"

    assert results[2]["title"] == "Quiz 3 - Finite Automata"

    print("  ✅ test_realistic_ncsu_moodle passed")
    return results


if __name__ == "__main__":
    print("\n🧪 Testing Moodle Scraper\n" + "=" * 30)
    test_timeline_block()
    test_course_overview_block()
    test_generic_table()
    test_list_items()
    test_empty_html()
    test_extract_assignment_detail()
    test_realistic_ncsu_moodle()
    print("\n" + "=" * 30)
    print("✅ All tests passed!\n")