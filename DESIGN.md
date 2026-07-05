# Design System: arXiv Explorer — Optical Laboratory

## 1. Visual Theme & Atmosphere

A "Speculative Academic" instrument dashboard — part scholarly archive, part data terminal. The interface reads as a pragmatic research workstation for scanning, querying, and mapping the arXiv corpus. Visual hierarchy is driven by content: data visualizations, search results, and scientific metadata dominate the canvas. Chrome exists to frame content, not compete with it.

The aesthetic is dark-first (Obsidian & Neon Ink) with a secondary light theme (Blueprint Paper). Decorative effects are minimal — no scanlines, glitch text, or crosshair overlays. The interface fades into the background so the research data takes focus.

- **Density:** 8/10 (Content-first — dense results lists, compact metadata)
- **Atmosphere:** 3/10 (Chrome is restrained; the data provides the character)
- **Motion:** 2/10 (Static unless interactive — pulsing dots for loading only)

## 2. Color Palette & Roles

### Dark Theme (Primary — "Obsidian & Neon Ink")
- **Obsidian Void** (#0a0a0a) — Primary background / surface base
- **Surface Container** (#181818) — Card and panel fill
- **Surface Container Low** (#1c1b1b) — Elevated panels
- **Surface Container High** (#2a2a2a) — Hover states, active filters
- **Surface Container Highest** (#353534) — Pressed states
- **Ion White** (#e5e2e1) — Primary text / on-surface
- **Signal Gray** (#b9cacb) — Secondary text / on-surface-variant
- **Outline** (#849495) — Structural borders, 1px grid lines
- **Outline Dim** (#3a494b) — Subtle dividers, muted borders
- **Ion Blue** (#00dbe7) — Single accent for links, active states, focus rings, data tracers
- **Phantom Violet** (#d0bcff) — Secondary associations, metadata tags, archival links
- **Signal Green** (#22c55e) — Positive trends, growth indicators
- **Warning Red** (#ef4444) — Negative trends, critical states

### Light Theme (Secondary — "Blueprint Paper")
- **Canvas** (#f4f4f0) — Primary background
- **Pure Surface** (#ffffff) — Card and container fill
- **Ink** (#18181b) — Primary text
- **Steel** (#52525b) — Secondary text
- **Blueprint Line** (#d4d4d8) — Borders and structural lines
- **Blueprint Accent** (#007c8a) — Accent (darker Ion Blue for light mode)
- **Phantom Ink** (#5e35b1) — Secondary associations

## 3. Typography Rules

- **Display / Headlines:** Playfair Display — Track-tight, controlled scale. Used for H1 page titles and section headers only (not for body content or list items).
- **Body / UI / Data / Labels:** Space Mono — All functional UI, search results, data readouts, navigation, labels, and body copy. Reinforces the terminal/blueprint aesthetic. Two-typeface stack (Playfair + Space Mono); no sans-serif fallback.
- **Scale:**
  - Display (hero): `clamp(2.5rem, 5vw, 4rem)` — Homepage title only
  - Headline: `clamp(2rem, 4vw, 3rem)` — Page titles
  - Subhead: `clamp(1.5rem, 3vw, 2.5rem)` — Section headers (detail pages)
  - Body: `0.875rem` (14px) — Functional UI
  - Label Caps: `0.75rem` (12px) uppercase `0.1em` tracking — Micro-labels
  - Data: `0.8125rem` (13px) — Data readouts
- **Content Density:** Paper titles in result lists use `0.875rem` mono bold without extra spacing. Metadata (authors, year, citations) runs at `0.75rem` on the same line. No unnecessary line breaks between title and metadata.
- **Banned:** Inter, Geist, generic system fonts for premium contexts. Generic serif fonts (Times New Roman, Georgia) banned — use Playfair Display exclusively for serif needs. `--font-body` uses Space Mono, matching the terminal identity.

## 4. Component Stylings

- **Search Input:** Bold and prominent — 2px border, `1rem` font size, full-width with generous padding. High-contrast hover/focus states with Ion Blue glow. Terminal-style placeholder is lowercase and descriptive ("Search arXiv papers…" rather than "QUERY SIGNAL…"). The search bar is the primary action on the Papers page and should dominate visually.
- **PaperCard (search results):** Title-first layout with compact metadata inline. No card borders — only a bottom divider between items. Title uses `0.875rem` mono bold with hover color change. Authors, year, and citation count are on a single `0.75rem` line below. Padding: `py-3.5` for dense scrolling.
- **Buttons:** Primary: pill-shaped with Ion Blue solid fill (#00dbe7) and black text (#0a0a0a). Secondary: 0px radius rectangle with 1px Ion Blue border. No outer glow on static state.
- **Loading States:** Pulsing dot (Ion Blue glow) for inline loading. No skeletal shimmers, no circular spinners.
- **Data Tables:** Full-width tables with `divide-y` rows, mono body text, `label-caps` headers. Minimal borders.
- **Focus Rings:** Ion Blue glow outline. No offset, 2px width.

## 5. Layout Principles

- **Sidebar:** Fixed left 56px (w-14) navigation with flat icon buttons. No "INSTRUMENT" label, no "UNIT 01" decoration, no pulsing status dot. Dominant color only for active state.
- **Content Width:** `max-w-6xl` (1152px) for main pages, `max-w-4xl` (896px) for detail pages, `max-w-3xl` (768px) for text-heavy pages (About).
- **Page Headers:** Left-aligned with 4px Ion Blue border-left accent. `label-caps` subtitle + Playfair Display H1. No extra decorative elements.
- **Responsive:** Single-column collapse below 768px. Sidebar becomes bottom nav on mobile.
- **Section Separation:** 1px solid borders (outline at 20-30% opacity) between sections.
- **Spacing:** Consistent `py-14` top padding for pages, `mb-10` for headers.
- **No decorative overlays:** No scanlines, no crosshair grids, no dot-matrix backgrounds on content areas. Visual interest comes from the data (graphs, tables, charts) and the dark/light surface hierarchy.

## 6. Motion & Interaction

- **Transitions:** `transition-colors` for interactive elements. No spring physics or elaborate animations.
- **Pulse Loop:** Only used for loading states (pulsing dot). Never used for decorative "LIVE" badges.
- **Hover Effects:** Border color changes or background tint (`bg-surface-container-low`) on interactive rows. No shimmer, no glitch, no translate transforms.
- **Performance:** No animation on static elements. Animations run only in response to user interaction.
- **Hardware Acceleration:** Not needed — animations are limited to CSS transitions and pulse keyframe.

## 7. Content-First Principles

1. **Content is the product.** Search results, paper details, tables, and graphs are the primary visual. Chrome (borders, headers, navigation) must not compete.
2. **Dense lists over spaced cards.** Search results, author rankings, and category lists use compact vertical layouts with minimal padding between items. Scan through content quickly — don't make each item a destination.
3. **One accent color only.** Ion Blue is the single accent for links, active states, and the header border accent. Phantom Violet is reserved for secondary data labeling only. Oversaturating with multiple colors dilutes the signal.
4. **No atmospheric effects.** Scanline, glitch, crosshair grids, and dot-matrix backgrounds are removed from content areas. The error page is the sole exception — dot-matrix as a full-page backdrop matches the "terminal fault" tone there.
5. **Search is the primary action.** On the Papers page, the search input uses `border-2` with heavier padding and larger font size. It should be the first thing a user sees and the most visually prominent element on the page.
6. **Headlines frame, they don't decorate.** Playfair Display is used for page titles (H1) and section headers (H2) only. Never for body text, labels, or data values. Keep headline sizes proportional to the content they introduce.

## 8. Anti-Patterns (Banned)

- No emojis anywhere in the UI
- No Inter font family
- No generic serif fonts (Times New Roman, Georgia, Garamond, Palatino)
- No pure black (#000000) — use Obsidian Void (#0a0a0a)
- No neon/outer glow shadows on static elements — glow is reserved for active/focus states
- No oversaturated accents — Ion Blue at #00dbe7 is the maximum saturation allowed
- No custom mouse cursors
- No atmospheric effects (scanlines, glitch text, crosshair overlays, dot-matrix backgrounds on content) — the error page is the sole exception: dot-matrix as a full-page background is acceptable there, consistent with the "terminal fault" tone
- No 3-column equal card layouts — use asymmetric grids or 2-column zig-zag
- No fake round numbers or percentages
- No AI copywriting clichés ("Elevate", "Seamless", "Unleash", "Next-Gen", "Revolutionary")
- No filler UI text: "Scroll to explore", "Swipe down", scroll arrows, bouncing chevrons
- No broken Unsplash links — use picsum.photos or SVG data URIs
- No centered Hero sections (variance > 4 forces asymmetric layout)
- No shadow-based elevation — use luminance, glow, and border color instead
- No floating labels in form inputs
- No circular spinners for loading — use pulsing dots only
- No decorative "LIVE" badges or "UNIT" labels that don't convey real information
