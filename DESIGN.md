# SentinelReview — Visual & UI Design System

## 1. Design Read & Aesthetic Direction
> **Design Read**: Technical developer tool / security inspection cockpit for engineers and hackathon judges, with a high-contrast dark-mode Linear/terminal aesthetic, monospace accenting, and clear severity visual hierarchy.

### The Three Dials
- **`DESIGN_VARIANCE: 4`** — Structured, clean, purpose-driven cockpit layout with asymmetric inspector cards.
- **`MOTION_INTENSITY: 3`** — Restrained, snappy micro-interactions (pulse on review, copy feedback, tab transitions).
- **`VISUAL_DENSITY: 7`** — Information-dense layout maximizing code visibility, diff clarity, and actionable fix suggestions.

---

## 2. Color Palette & Semantic Tokens

| Token | Hex | Role / Context |
| :--- | :--- | :--- |
| `--bg-base` | `#0B0F17` | Canvas background, dark obsidian |
| `--bg-surface` | `#111827` | Card & inspector surfaces |
| `--bg-subtle` | `#1E293B` | Interactive hover & secondary backgrounds |
| `--border-subtle` | `#1F2937` | Component boundaries and card outlines |
| `--border-accent` | `#38BDF8` | Focus rings & primary interactive cues |
| `--text-primary` | `#F9FAFB` | Main headlines, code, and key labels |
| `--text-muted` | `#94A3B8` | Body explanations, metadata, timestamps |
| `--color-high` | `#EF4444` | High severity / Security vulnerabilities / Injections |
| `--color-med` | `#F59E0B` | Medium severity / Logic bugs / Warnings |
| `--color-low` | `#64748B` | Low severity / Style conventions / Nitpicks |
| `--color-success`| `#10B981` | Verification pass badge / Safe indicators |
| `--code-bg` | `#030712` | Monospace code snippet background |

---

## 3. Typography & Scale

- **Display & UI Font**: System sans-serif stack (`ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`).
- **Code & Snippets**: High-legibility monospace stack (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`).

### Scale
- **Header Title**: `20px` / `600` weight with subtle tracking (`-0.02em`).
- **Section Headers**: `14px` / `600` uppercase tracking (`0.05em`).
- **Finding Card Title**: `15px` / `600` weight.
- **Body / Explanation**: `13px` / `400` with `1.5` line-height.
- **Code & Diffs**: `12px` / `400` with monospace formatting.

---

## 4. Component Standards

### 4.1 Header & Control Bar
- Minimal top bar containing the SentinelReview badge, live version tag, sample selector, language select dropdown, and primary review trigger button.
- Clear status pill showing backend model connectivity (`Groq Active`, `Gemini Fallback`, or `SAST Only`).

### 4.2 Metrics & Verification Banner
- Real-time telemetry strip displayed immediately upon review completion:
  - High / Medium / Low issue counts.
  - **False Positives Filtered** badge (emphasizing the adversarial verification moat).
  - Provider indicator badge with latency notice.

### 4.3 Finding Card Architecture
- 4px colored vertical stripe along the left border indicating severity (`#EF4444` / `#F59E0B` / `#64748B`).
- Badge row: Category (`Security`, `Bug`, `Style`), CWE badge (e.g., `CWE-89`), confidence percentage (e.g., `94%`), source tag (`semgrep`, `llm`, `injection-scan`), and line indicator (`Line 14`).
- Plain-English explanation detailing why the issue matters in production.
- Monospace fix snippet equipped with a one-click **"Copy Fix"** clipboard button.

### 4.4 Zero CDN & Offline Guarantee
- All styles, SVGs, and scripts are embedded directly inside `static/index.html`.
- Zero network requests required to render the interface.
