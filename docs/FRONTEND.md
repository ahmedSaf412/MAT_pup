# Frontend Technology Documentation

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Next.js** | 14.x | React framework with SSR, file-based routing, API routes |
| **React** | 18.x | Component-based UI library |
| **MediaPipe Pose** | Latest | In-browser real-time pose estimation (33 landmarks) |
| **Chart.js** | 4.x | Training stats & progress charts |
| **react-chartjs-2** | 5.x | React wrapper for Chart.js |
| **Axios** | 1.x | HTTP client for REST API calls |
| **CSS (Vanilla)** | — | Dark-themed design system with glassmorphism |

---

## Why These Technologies?

### Next.js 14
- **Server-Side Rendering (SSR)** for SEO on marketing pages
- **File-based routing** — each page is a file in `src/app/`
- **API routes** (optional) for lightweight proxying
- Built-in **image optimization** and **code splitting**
- Excellent TypeScript support (can add later)

### MediaPipe Pose (In-Browser)
- **Runs entirely in the browser** — no video sent to server (privacy!)
- Uses Google's **BlazePose** model under the hood
- Outputs **33 3D landmarks** per frame at 30+ FPS on modern hardware
- Landmarks include all major joints: shoulders, elbows, wrists, hips, knees, ankles
- Only the **landmark coordinates** (tiny JSON) are sent to the backend via WebSocket

### Chart.js
- Lightweight, responsive charts
- Line charts for progress over time, radar charts for move accuracy breakdown
- Easy to integrate with React via `react-chartjs-2`

---

## Pages & Routes

| Route | Page | Auth Required? |
|-------|------|---------------|
| `/` | Landing page — hero section, features, CTA | No |
| `/login` | Login form | No |
| `/register` | Register form | No |
| `/dashboard` | User dashboard — stats, history, charts | Yes |
| `/train` | **Core page** — live webcam + AI classification + corrections | Yes |
| `/profile` | User profile — edit name, belt level | Yes |

---

## Key Components

### `PoseCanvas.js`
- Overlays a `<canvas>` on top of the `<video>` element
- Draws MediaPipe skeleton with colored lines
- **Highlights joints needing correction in red**
- Updates at the same framerate as the webcam

### `CorrectionPanel.js`
- Side panel showing:
  - Current classified move name (e.g., "Front Kick")
  - Confidence bar (0–100%)
  - List of corrections (e.g., "Extend knee further", "Keep guard up")
- Updates in real time via WebSocket data

### `SessionHistory.js`
- Table/list of past training sessions
- Shows date, duration, score, moves practiced
- Click to view detailed session breakdown

### `StatsChart.js`
- Line chart: overall score over time
- Radar chart: accuracy per move type
- Uses Chart.js with animated transitions

---

## MediaPipe Integration Flow

```
┌────────────┐     ┌──────────────┐     ┌────────────────┐
│  Webcam    │────▶│ MediaPipe    │────▶│ PoseCanvas     │
│  <video>   │     │ Pose         │     │ (draw skeleton)│
└────────────┘     │ (in-browser) │     └────────────────┘
                   └──────┬───────┘
                          │ 33 landmarks (x, y, z, visibility)
                          ▼
                   ┌──────────────┐     ┌────────────────┐
                   │ WebSocket    │────▶│ Backend        │
                   │ Client       │     │ (classify +    │
                   │ (send JSON)  │     │  correct)      │
                   └──────────────┘     └────────┬───────┘
                                                 │ {move, confidence, corrections[]}
                                                 ▼
                                        ┌────────────────┐
                                        │ CorrectionPanel│
                                        │ (update UI)    │
                                        └────────────────┘
```

---

## Design System

- **Theme**: Dark mode with deep navy/midnight blue background
- **Accent colors**: Electric blue `#00D4FF`, vibrant orange `#FF6B35`
- **Cards**: Glassmorphism (semi-transparent, backdrop blur, subtle border)
- **Typography**: Google Fonts — **Inter** (body), **Outfit** (headings)
- **Animations**: CSS `@keyframes` for fade-ins, slide-ups, glow effects
- **Responsive**: Mobile-first, breakpoints at 768px and 1024px

---

## State Management
- **React Context** for auth state (user token, profile data)
- **Local state** (`useState`) for component-level UI
- No Redux needed — the app is straightforward enough

## Environment Variables
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/pose
```
