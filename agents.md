# MLH 2026 — AI Toolkit App

## Overview
Never commit without my permission
Don't check for changes in github without permission
Always get my permission before you start making test cases

A **local-only** AI toolkit that runs entirely on your laptop. No cloud deployment, no API proxies, no third-party servers. FastAPI serves a browser frontend, and everything — camera, mic, file system, mouse control — happens on `localhost`.

Built for **MLH 2026**.

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