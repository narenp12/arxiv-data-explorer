---
name: Quantum Archivist
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#849495'
  outline-variant: '#3a494b'
  surface-tint: '#00dbe7'
  primary: '#e1fdff'
  on-primary: '#00363a'
  primary-container: '#00f2ff'
  on-primary-container: '#006a71'
  inverse-primary: '#00696f'
  secondary: '#d0bcff'
  on-secondary: '#3c0091'
  secondary-container: '#571bc1'
  on-secondary-container: '#c4abff'
  tertiary: '#f7f8f8'
  on-tertiary: '#2f3131'
  tertiary-container: '#dbdbdb'
  on-tertiary-container: '#5e6060'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#74f5ff'
  primary-fixed-dim: '#00dbe7'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f54'
  secondary-fixed: '#e9ddff'
  secondary-fixed-dim: '#d0bcff'
  on-secondary-fixed: '#23005c'
  on-secondary-fixed-variant: '#5516be'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 64px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Space Mono
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Space Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: Space Mono
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.0'
    letterSpacing: 0.1em
  code-data:
    fontFamily: Space Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: -0.01em
spacing:
  unit: 4px
  gutter: 1px
  margin-page: 48px
  container-max: 1440px
  col-gap: 24px
  row-gap: 24px
---

## Brand & Style

The design system is built upon the "Speculative Academic" narrative—a fusion of rigorous scholarly tradition and high-precision futuristic instrumentation. It is designed for researchers, data architects, and curators of complex digital ecosystems. The emotional response is one of "Technical Authority": the UI should feel like a state-of-the-art optical terminal used to scan deep-space archives.

The design style is **Technical Brutalism mixed with Blueprint Minimalism**. It prioritizes information density and structural clarity. Visual interest is generated through 1px wireframes, dot-matrix patterns, and high-frequency "ion" glows against deep obsidian voids. The interface does not hide its construction; it celebrates it through visible grid lines, coordinate systems, and layered data "scans."

## Colors

The "Obsidian & Neon Ink" palette is optimized for high-contrast, low-light environments. 

- **Primary (Ion Blue):** Reserved for active data states, critical focus indicators, and interactive "tracers." It represents live energy.
- **Secondary (Phantom Violet):** Used for archival links, metadata tags, and secondary associations. It evokes a sense of depth and mystery.
- **Surface (Obsidian):** The background is a true dark (#0a0a0a) to allow the 1px borders and neon highlights to "pop" without visual muddying.
- **Foreground (High-Contrast White):** Typography uses pure white or high-gray for maximum legibility against the dark void.

## Typography

Typography is used to represent the intersection of the "Academic" and the "Quantum." 

- **The Scholarly Voice (Playfair Display):** Use for large display headings. It provides the intellectual weight of a printed thesis. Treat it as a "specimen"—often centered or placed with significant white space.
- **The Technical Voice (Space Mono):** Use for all functional UI, data readouts, and body copy. It reinforces the "terminal" aesthetic. High density is encouraged for data-heavy sections. 
- **Hierarchy Tip:** Use `label-caps` for section headers and technical metadata to create a "blueprint" feel.

## Layout & Spacing

The layout philosophy follows a **Fixed Architectural Grid**. Every element must align to a visible or invisible 4px baseline. 

- **The 1px Rule:** Layout sections should be separated by 1px solid borders in a low-opacity white (10-15%) to simulate an engineering drawing or "blueprint."
- **Dot-Matrix Overlays:** Use a subtle repeating dot pattern (2px dots, 16px apart) on background layers to create a sense of scale and coordinate mapping.
- **Multi-layered Scan:** Use offset margins and "floating" data panels to create depth. Elements do not just sit on the page; they are "projected" into the workspace.
- **Mobile Adaptivity:** On mobile, the 1px borders remain, but the layout collapses into a single column of "data cards." Margins reduce to 16px.

## Elevation & Depth

This design system rejects traditional shadows in favor of **Luminance and Opacity**.

- **Glassmorphism:** Primary containers use a backdrop-filter (blur: 20px) with a semi-transparent Obsidian background (60%). This suggests layers of data being viewed through a lens.
- **Interactive Shimmer:** Instead of a shadow, an active element (like a focused card) receives a 1px "shimmer" border—a gradient stroke that moves around the perimeter using Ion Blue and Phantom Violet.
- **Depth Layers:**
    - *Layer 0 (Base):* Pure Obsidian with Dot-Matrix.
    - *Layer 1 (Blueprint):* 1px grid lines and wireframes.
    - *Layer 2 (Content):* Glassmorphic panels with high blur.
    - *Layer 3 (Interface):* High-contrast text and interactive neon components.

## Shapes

The shape language is a study in extremes. 

1.  **Hard Precision:** All standard containers, inputs, and layout blocks have **zero radius (0px)**. This communicates structural rigidity and technical accuracy.
2.  **Organic Fluidity:** Interactive triggers, "Pills," and data tags use **Maximum Radius (Pill-shaped)**. This creates a clear visual distinction between "Structural" elements and "Interactive/Status" elements.

Avoid intermediate rounded corners (e.g., 4px or 8px). It is either a sharp corner or a full pill.

## Components

- **Buttons:** Primary buttons are pill-shaped with a solid Ion Blue fill and black text. Secondary buttons are 0px sharp rectangles with a 1px Ion Blue border and "shimmer" hover effect.
- **Data Chips:** Small pill-shaped tags using Phantom Violet backgrounds at 20% opacity with 100% opacity text. Used for categorization.
- **Input Fields:** Sharp 0px rectangles with a 1px bottom border only. On focus, the border expands to 1px on all sides with a "glow" effect.
- **Cards:** Glassmorphic panels with 1px white (10% opacity) borders. Headers within cards should use `label-caps`.
- **Animated Tracers:** Use thin, animated lines (1px) that travel along the grid gutters to indicate background processing or data flow.
- **Checkboxes:** Sharp 1px squares. When checked, they fill with an "X" shape rather than a checkmark, maintaining the technical/blueprint aesthetic.
- **Status Indicators:** Use a "scanning" animation—a horizontal Ion Blue line that moves vertically across an element to show it is being updated or verified.