# Lab 1: URL Shortener

## Objective

Build and deploy a URL shortener using AI-assisted development to experience the "Vibe Coding" workflow.

**Time Allotted:** 1 hour 15 minutes

## Learning Goals

- Practice AI-assisted scaffolding
- Experience iterative development with AI
- Deploy to Vercel (frontend) and Railway (backend)
- Understand the human-AI collaboration loop

## Project Overview

You'll build a URL shortener with:

- **Backend:** Python FastAPI (generates short codes, stores mappings)
- **Frontend:** TypeScript Next.js (simple UI)
- **Deployment:** Vercel (frontend) + Railway or similar (backend API)

```
┌─────────────────────────────────────────────────────────────┐
│                    URL Shortener Architecture               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User → [Next.js Frontend] → [FastAPI Backend] → [SQLite]   │
│                                                             │
│  1. User enters long URL                                    │
│  2. Frontend calls /api/shorten                             │
│  3. Backend generates short code                            │
│  4. Backend stores mapping in SQLite                        │
│  5. Frontend displays short URL                             │
│                                                             │
│  Redirect Flow:                                             │
│  User visits short URL → Backend looks up → Redirects       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

### Backend

- `POST /shorten` endpoint: accepts `{"url": "https://..."}` and returns `{"short_code": "abc123", "short_url": "..."}`
- `GET /{short_code}` endpoint: redirects to the original URL
- Use SQLite for storage
- Generate 6-character alphanumeric codes
- Add input validation for URLs
- Handle duplicate URLs (return existing short code)

### Frontend

- Single page with input field for URL
- Submit button that calls the shorten API
- Display the shortened URL with copy button
- Show loading state during API call
- Handle errors gracefully
- Responsive design

### Deployment

- Backend deployed to Railway (or similar)
- Frontend deployed to Vercel

## Deliverables

**Live:** frontend https://taller-url-shortener-gamma.vercel.app · backend https://backend-production-7f82d.up.railway.app

- [x] Backend running locally and tests passing
- [x] Frontend running locally and connecting to backend
- [x] Backend deployed to Railway (or similar)
- [x] Frontend deployed to Vercel
- [x] End-to-end URL shortening works

## Extension Challenges (If Time Permits)

- [ ] **Analytics:** Track click counts for each short URL
- [ ] **Custom Codes:** Allow users to specify custom short codes
- [ ] **Expiration:** Add optional expiration dates for URLs
- [ ] **QR Codes:** Generate QR code for short URLs

## Reflection Questions

After completing the lab, consider:

1. How did AI assistance change your development speed?
2. What did you have to manually adjust in the AI-generated code?
3. When did you need to provide more context to the AI?
4. What would you do differently next time?
