# MLH 2026 — AI Toolkit App

## Overview

A **local-only** AI toolkit that runs entirely on your laptop. No cloud deployment, no API proxies, no third-party servers. FastAPI serves a browser frontend, and everything — camera, mic, file system, mouse control — happens on `localhost`.

Built for **MLH 2026**.

---

## 🧭 AI Context — Implementation Status (2026-09-26)

> This section is written for AI coding agents to get up to speed fast.
> Update this section as the project evolves.

### Active Branch: `feature/assignmenthelp`

Current active work is on the **Dashboard Inspector** (Tool #3).
The other two tools (Study Buddy, Lecture Note-Taker) are frontend shells with stub backends.

### Implementation Status

| Tool | Status | What's Done | What's Missing |
|---|---|---|---|
| 📋 Dashboard Inspector | **✅ Complete** | Full scraper, Tab-navigation description extraction, Gemini study points + interactive multiple-choice quiz, PyAutoGUI browser automation, JSON cache, polished HTMX frontend | No bookmarklet yet |
| 📄 Study Buddy | 🟡 **Stub** | Frontend shell (drag-drop, loading spinner, quiz container), router stubs, Alpine.js state | `services/pdf_parser.py` is a stub, `routers/study_buddy.py` returns placeholder HTML, no Gemini quiz generation |
| 🎙️ Lecture Note-Taker | 🟡 **Stub** | Frontend shell (recording button, timer, notes/flags panels), WebSocket endpoint stub | `services/audio_processor.py` is stub, no audio streaming, no Gemini multimodal integration |

### Dashboard Description Extraction Flow

The scraper no longer uses URLs in new tabs. Instead:

1. **`open_dashboard_and_grab()`** — Opens Moodle dashboard in a new tab, Ctrl+A→Ctrl+C to grab rendered text, keeps the tab open (no Ctrl+W)
2. **`parse_dashboard()`** — Parses the dashboard text for assignment list (6 strategies)
3. **`grab_assignment_descriptions()`** — On the same open dashboard tab:
   ```
   Tab 22x → focus first assignment link
   Enter → open assignment page
   Wait 2s → let it load
   Ctrl+A → Ctrl+C → store rendered text in `_page_html`
   Alt+Left → back to dashboard
   Wait 1.5s → dashboard reloads
   Tab 2x → focus next assignment
   Repeat for each assignment
   Ctrl+W → close dashboard tab when done
   ```
4. **`enrich_assignments_with_descriptions()`** — For each `_page_html`:
   - Detects plain-text vs HTML (rendered text starts with "Skip to main..." not `<`)
   - For plain-text: finds assignment content via markers (`Completion requirements`, `To do:`, `Due:`, `Opened:`) and extracts from there until `Submission status`, `Attempt number`, `Jump to...`
   - Deduplicates consecutive lines, strips Moodle chrome
   - Stores clean text in `description` key (overwriting dashboard placeholder)
   - Deletes `_page_html` (never reaches frontend)

### Timing (all sleeps)

| Step | Sleep |
|---|---|
| Dashboard load wait | 2s |
| Enter → assignment page load | 0.5s + 2s = 2.5s |
| Alt+Left → dashboard reload | 0.3s + 1s = 1.3s |
| Tab between assignments | 0.05s × 2 = 0.1s |
| **Per assignment total** | **~3.9s** |

Tab counts: `tab_first=22`, `tab_next=2` — configurable parameters.

### Plain-Text Extraction Markers

`extract_assignment_detail()` uses content-section markers:
- **Start:** `Completion requirements`, `To do:`, `Due:`, or `Opened:`
- **End:** `Submission status`, `Attempt number`, `Jump to...`, `Grading status`, `Time remaining`, `Last modified`, or `Submission comments`

### Gemini Integration

`services/gemini.py` is shared across all three tools:
- Lazy-loads the `google-genai` client (graceful stub when no API key present)
- `ask_gemini(prompt, context, system_prompt)` — freeform response
- `ask_gemini_structured(prompt, context, system_prompt)` — adds markdown-structure instruction
- Default model: `gemini-3.6-flash`

API key is set in `.env` — AI features are active.

### HTMX Pattern (Dashboard Tool)

All Dashboard Inspector interactions follow the same HTMX pattern:

```
User clicks "Study Points" → POST /dashboard/study-points → Gemini → HTML <div> with bullet list → hx-target swap
User clicks "Generate Quiz" → POST /dashboard/quiz → Gemini → HTML <div> with Q&A → hx-target swap
User clicks "Grab Instructions" → POST /dashboard/grab-instructions → PyAutoGUI → HTML <div> with links + text → hx-target swap
```

Each assignment card has a `.results-area` div that receives the swap, keeping cards independent.

Cards send `description` (the scraped assignment text) as hidden form data in `hx-vals` — the user never sees it, but Gemini gets the full assignment context.

### Jinja2 Rendering

Templates use a direct Jinja2 `Environment` (not Starlette's `Jinja2Templates`) for Python 3.14 compatibility with `datetime.strptime` changes. Each router that needs templates creates its own `_jinja_env` pointing to `templates/`.

### Quiz Format

Quiz is rendered as interactive multiple-choice with plain JavaScript (not Alpine.js):
- 3 questions per quiz, each with 4 options (A-D)
- Click an answer → immediately shows ✓ (green) or ✗ (red) + explanation
- Once answered, locked — button is removed to prevent re-calling Gemini
- Quiz parsing/rendering lives in `routers/quiz_helpers.py`
- Gemini is instructed to avoid LaTeX (`$...$`) — uses plain text formulas

### Dashboard Endpoints

```
GET  /dashboard                          → Dashboard page (HTML)
POST /dashboard/inspect                  → Paste dashboard HTML → assignment cards
POST /dashboard/grab                     → PyAutoGUI: open dashboard → parse → Tab-navigate assignments → close tab → cards + console.log dump
POST /dashboard/scrape-only              → Paste HTML → parse only (no Gemini, debugging)
POST /dashboard/study-points             → Gemini → study topics for one assignment (uses description from form data)
POST /dashboard/quiz                     → Gemini → practice quiz for one assignment (uses description from form data)
POST /dashboard/grab-instructions        → PyAutoGUI: one-off assignment page grab → instructions + Google Doc links
GET  /dashboard/debug/sample             → Parse sample HTML → show results
GET  /dashboard/debug/sample-raw         → Return raw sample HTML (for frontend testing)
```

### Console Output

Server terminal prints full description text after grab. Browser Chrome console gets a brief summary (titles + char counts).

### Stubs to Fill (when switching branches)

1. **Study Buddy:** Implement `services/pdf_parser.py` with PyMuPDF, then wire `routers/study_buddy.py` POST handlers to call `ask_gemini` for quiz generation and answer explanation. The frontend is fully ready.
2. **Lecture Note-Taker:** Implement `services/audio_processor.py` for audio chunking, connect WebSocket in `routers/lecture.py` to Gemini's streaming multimodal API, push real-time notes back as JSON. The frontend has the WebSocket connection pattern and Alpine.js state ready.

---

## Stack

### Backend — FastAPI (Python)

| Layer | Technology |
|---|---|
| **Server** | FastAPI + Uvicorn |
| **AI** | Google Gemini API (via `google-genai` SDK) |
| **System control** | `pyautogui` (mouse, keyboard, screenshots), `pynput` (global listeners), `mss` (fast screen capture) |
| **Media capture** (backend) | `opencv-python` (camera), `sounddevice` (microphone) |
| **File handling** | `python-multipart` (uploads), standard `pathlib` |
| **PDF parsing** | `PyMuPDF` / `pdfplumber` |

### Frontend — Alpine.js + HTMX (no build step)

| Layer | Technology |
|---|---|
| **Reactivity** | Alpine.js — one `<script>` tag, reactive state in HTML |
| **Server calls** | HTMX — click buttons, FastAPI returns HTML snippets |
| **WebSocket** | Native browser `WebSocket` API (for lecture audio/video streaming) |
| **Media capture** | Browser `getUserMedia` (camera, mic, screen share) |
| **Styling** | Tailwind CSS (via CDN script tag) |
| **Build step** | **None** — all frontend is plain HTML served by FastAPI |

> **Why no build step?** Alpine + HTMX are drop-in script tags. No webpack, no Vite, no `npm run build`. One terminal, one server (`uvicorn`), refresh the page.

---

## The Three Tools

### 1. 🎙️ Live Lecture Note-Taker

**What it does:**
Records a lecture in real time via the browser's microphone (or camera for slides). Streams audio to the FastAPI backend over WebSocket. Gemini transcribes and generates structured notes, flags confusing concepts, and syncs notes to slide timestamps.

**Data flow:**
```
Browser mic (getUserMedia)
    │
    ├─ Audio chunks ──WebSocket──→ FastAPI
    │                                   │
    │                              Gemini API
    │                                   │
    ◄── JSON (notes, flags, timestamps) │
    │
Browser renders structured notes + flag list
```

**Key challenges:**
- Real-time audio chunking and streaming over WebSocket
- Chunking audio for Gemini's context window
- Slide detection and timestamp alignment (via camera or manual slide-advance button)
- Clean note formatting in the UI

**Endpoints:**
```
GET  /                    → Lecture tool page (HTML)
WS   /ws/lecture          → Audio stream → Gemini → notes back
GET  /lecture/history     → Past lecture notes
```

---

### 2. 📄 Study Buddy from PDFs

**What it does:**
Drop in lecture slides or a textbook chapter. Gemini reads the PDF text and generates practice quizzes (multiple choice, short answer). When you get one wrong, it explains the mistake conversationally — like a tutor walking you through it.

**Data flow:**
```
Upload PDF (drag-drop or file input)
    │
    ├─ PDF bytes ──POST──→ FastAPI
    │                         │
    │                    Extract text (PyMuPDF)
    │                         │
    │                    Gemini → quiz questions
    │                         │
    ◄── HTML quiz snippet ────│
    │
User answers questions
    │
    ├─ Answer ──POST──→ FastAPI
    │                      │
    │                 Gemini → explanation
    │                      │
    ◄── HTML explanation ──│
```

**Key challenges:**
- PDF text extraction quality (tables, diagrams, math)
- Prompt engineering for good quiz questions
- Keeping the conversational explainer natural
- Session state — track which questions were wrong

**Endpoints:**
```
GET  /study-buddy         → Study buddy page (HTML)
POST /study-buddy/upload  → Upload PDF, get quiz (HTML response via HTMX)
POST /study-buddy/answer  → Submit answer, get explanation (HTML)
```

---

### 3. 📋 Dashboard Inspector (NCSU Moodle)

**What it does:**
Inside the NC State Moodle app, scans your dashboard for assignments due soon. Inspects each assignment's details and generates a list of topics to study, plus an option to create a practice quiz for each assignment.

**Data flow:**
```
Browser (user logs into Moodle in an iframe or side-panel)
    │
User clicks "Inspect Dashboard"
    │
    ├─ Dashboard HTML ──POST──→ FastAPI
    │                              │
    │                         Parse assignments (BeautifulSoup)
    │                              │
    │                         For each assignment:
    │                           │
    │                           ├─ Fetch assignment detail page
    │                           ├─ Gemini → study points + quiz
    │                              │
    ◄── HTML results (HTMX swap) ──│
```

**Key challenges:**
- Moodle authentication — user logs in via their own browser, we just need the page HTML
- Scraping Moodle's DOM (may change, need robust selectors)
- Delicate line between "helpful" and "doing the work for them" — focus on *study points*, not answers
- NCSU Moodle-specific selectors

**Endpoints:**
```
GET  /dashboard            → Dashboard inspector page (HTML)
POST /dashboard/inspect   → Submit Moodle dashboard HTML → get assignments + study points
POST /dashboard/quiz      → Generate quiz for a specific assignment
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Localhost :8000                      │
│                                                          │
│   FastAPI Server                                         │
│   ┌─────────────────┐    ┌─────────────────────────┐    │
│   │  Static Files    │    │  API / WebSocket Routes  │    │
│   │  (HTML, CSS, JS) │    │                         │    │
│   │                  │    │  /lecture               │    │
│   │  index.html      │    │  /study-buddy           │    │
│   │  lecture.html    │    │  /dashboard             │    │
│   │  study-buddy.html│    │  /ws/lecture            │    │
│   │  dashboard.html  │    │                         │    │
│   └─────────────────┘    │  ┌───────────────────┐   │    │
│                          │  │  Gemini Client    │   │    │
│                          │  │  (genai SDK)      │   │    │
│                          │  └───────────────────┘   │    │
│                          │  ┌───────────────────┐   │    │
│                          │  │  System Tools     │   │    │
│                          │  │  (pyautogui, mss, │   │    │
│                          │  │   sounddevice, cv2)│   │    │
│                          │  └───────────────────┘   │    │
│                          └─────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
           │
           │ HTTP + WebSocket (localhost only)
           ▼
┌─────────────────────────────────────────────────────────┐
│                  Browser (Chrome / Firefox)              │
│                                                          │
│   Frontend (Alpine.js + HTMX + Tailwind CDN)             │
│                                                          │
│   ┌──────────┐  ┌──────────────┐  ┌────────────────┐   │
│   │ Lecture  │  │ Study Buddy  │  │ Dashboard      │   │
│   │ (camera/ │  │ (PDF upload) │  │ Inspector      │   │
│   │  mic)    │  │              │  │ (Moodle scrape) │   │
│   └──────────┘  └──────────────┘  └────────────────┘   │
│                                                          │
│   Built-in APIs: getUserMedia, WebSocket, File API       │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mlh2026/
│
├── main.py                 # FastAPI app, routes, startup
├── agents.md               # This file
├── README.md               # Project overview
│
├── static/
│   ├── styles.css          # Global styles (Tailwind + custom)
│   └── app.js              # Shared JS (WebSocket helpers, etc.)
│
├── templates/
│   ├── base.html           # Base layout (nav bar, Alpine/HTMX/Tailwind CDN)
│   ├── index.html          # Home / tool selector
│   ├── lecture.html        # Live Lecture Note-Taker page
│   ├── study-buddy.html    # Study Buddy page
│   └── dashboard.html      # Dashboard Inspector page
│
├── routers/
│   ├── lecture.py          # Lecture tool routes + WebSocket handler
│   ├── study_buddy.py      # Study Buddy routes
│   └── dashboard.py        # Dashboard Inspector routes
│
├── services/
│   ├── gemini.py           # Gemini API client (shared)
│   ├── pdf_parser.py       # PDF text extraction
│   ├── moodle_scraper.py   # Moodle parsing logic
│   └── audio_processor.py  # Audio chunking, streaming helpers
│
├── utils/
│   └── helpers.py          # Misc utility functions
│
└── requirements.txt        # Python dependencies
```

---

## Key Design Decisions

### No build step frontend
Alpine.js + HTMX + Tailwind via CDN. Three script tags. No `npm`, no `package.json`, no bundler. FastAPI serves HTML directly.

### WebSocket for streaming, HTTP/HTMX for everything else
The lecture tool is the only streaming endpoint. Study Buddy and Dashboard inspector are all request-response (HTMX swaps HTML snippets).

### User logs into Moodle in their own browser
The Dashboard Inspector doesn't handle Moodle auth — the user navigates to their Moodle dashboard, and either pastes the HTML or we use a bookmarklet / browser extension to send it to our backend.

### Gemini API key stored locally
The user sets `GEMINI_API_KEY` in a `.env` file. No cloud, no secrets server.

---

## Dependencies

```
fastapi
uvicorn[standard]
python-multipart
google-genai
PyMuPDF
beautifulsoup4
pyautogui
pynput
opencv-python-headless
sounddevice
mss
python-dotenv
Jinja2
```

---

## Future Ideas (if time)

- **Bookmarklet** for Dashboard Inspector — click it on the Moodle page, sends the DOM to the backend
- **Lecture history** — save past notes locally (SQLite or JSON files)
- **Spaced repetition** — flag concepts from lectures and get quizzed on them later
- **Screen capture** — let the lecture tool watch slides via screen share instead of camera
- **Audio playback** — replay a lecture segment from a timestamp in the notes