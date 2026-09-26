# MLH 2026 — Toolkit App

## Tools

### Study Buddy from PDFs
Drop in lecture slides or a textbook. Gemini generates practice quizzes and explains wrong answers conversationally — like having a tutor walk you through each mistake.

### Live Lecture Note-Taker
Record a class or lecture in real time. Gemini generates structured notes, flags concepts to review, and syncs everything to slide timestamps.

### Dashboard Inspector
Inside the Moodle NC State app, go through your dashboard to find assignments that are due soon. Inspect those assignments and generate a list of points to study, with the option to create a practice quiz for each one.

## Setup

```bash
npm install
cp .env.example .env.local
# Add your GEMINI_API_KEY to .env.local
npm run dev
```
