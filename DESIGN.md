---
name: BlenderShelf site
description: Restrained dark developer-tool landing page for the BlenderShelf Blender addon
colors:
  bg: "#0d0b0a"
  bg-elevated: "#18150f"
  bg-elevated-2: "#211d17"
  border: "#2a2620"
  border-strong: "#3c3630"
  text: "#f2f1ee"
  text-muted: "#99989f"
  accent: "#f5792a"
  accent-hover: "#ff9248"
  accent-text: "#14120f"
  warning: "#ffb84d"
typography:
  heading:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 1.2vw + 1.1rem, 2rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  display:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "clamp(1.9rem, 2.1vw + 1.35rem, 2.9rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, SFMono-Regular, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.06em"
rounded:
  base: "8px"
  card: "12px"
  hero: "14px"
  pill: "999px"
spacing:
  section-desktop: "4rem 2rem"
  section-mobile: "2.75rem 1.25rem"
  card-padding: "1.75rem"
  card-padding-mobile: "1.25rem"
components:
  cta:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-text}"
    rounded: "{rounded.base}"
    padding: "0.8rem 1.6rem"
  cta-hover:
    backgroundColor: "{colors.accent-hover}"
  cta-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.base}"
  panel:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-padding}"
  how-card:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-padding-mobile}"
---

# Design System: BlenderShelf site

## Overview

**Creative North Star: "The Restrained Dev-Tool Landing"**

A precise, warm-neutral dark page in the Linear/Raycast/Vercel register: one disciplined accent color, a coherent bilingual type family, hairline borders, and real product screenshots in plain frames do the persuading. There is no theme metaphor (no blueprint/schematic device, no Maya-shelf visual pun) — the world is the craft bar itself, played straight. This explicitly replaces a discarded dark-orange/Hanken-Grotesk execution that the owner named as anti-reference.

IBM Plex Sans/Mono was chosen specifically to render Latin and Cyrillic as one coherent family, since the site is fully bilingual (RU/EN, equally primary) and the prior font's weak Cyrillic support was the owner's original complaint.

**Key Characteristics:**
- Warm-neutral near-black ground, never pure black or cool-gray
- A single committed accent, used at CTA/wordmark/focus-ring/selection weight only — never scattered as chips or multiple tinted accents
- Hairline 1px borders throughout; no heavy shadows, no gradients
- Real product screenshots in plain 1px-bordered frames, never fake device chrome
- No kicker/eyebrow labels above headings anywhere on the page

## Colors

Warm-retinted near-black neutrals (R>G>B in every neutral swatch) carrying one orange accent at deliberately limited weight.

### Primary
- **Signal Orange** (`#f5792a`, accent): the one committed accent. Used at CTA backgrounds, the "Shelf" half of the wordmark, link color, focus-ring outline, and `::selection`. Hover state lightens to **Signal Orange Hover** (`#ff9248`). Text drawn on top of the accent uses **Accent Ink** (`#14120f`), not white.

### Neutral
- **Ground** (`#0d0b0a`): page background.
- **Elevated Surface** (`#18150f`): card/panel background one step up from Ground (`.panel`, `.hero-shot`, `.how-card`, video frame, sticky header at 82% opacity).
- **Elevated Surface 2** (`#211d17`): declared in `:root` as a second elevation step but not currently consumed by any rule — reserved, not yet reused. Don't invent a third-layer use for it without a real nested-surface need.
- **Hairline Border** (`#2a2620`): default 1px borders on cards, inputs, dividers between sections.
- **Border Strong** (`#3c3630`): hover state for card borders (`.how-card:hover`) — a small step up, not a color change.
- **Text** (`#f2f1ee`): headings, field labels, wordmark, card titles.
- **Text Muted** (`#99989f`): default body copy color, muted links, footer text.
- **Warning Amber** (`#ffb84d`): version-mismatch warning text and form error state only — never decorative.

### Named Rules
**The One Accent Rule.** `--accent` is the only saturated color on the page. It appears at CTA/wordmark/focus/selection moments only; it never tints a card background, an icon, or a body of text.

## Typography

**Display/Heading/Body Font:** IBM Plex Sans (with `system-ui, sans-serif` fallback)
**Label/Mono Font:** IBM Plex Mono (with `ui-monospace, SFMono-Regular, monospace` fallback)

**Character:** One family carries every UI role (headings and body alike, differentiated by weight and size, per the direction contract) — chosen because IBM Plex Sans and Plex Mono share full Latin+Cyrillic glyph coverage, so RU and EN render with the same visual voice instead of EN getting a designed face and RU getting a browser-substituted fallback. Weights loaded: 400/500/600/700 (Sans), 400/500 (Mono).

### Hierarchy
- **Display/H1** (600, `clamp(1.9rem, 2.1vw + 1.35rem, 2.9rem)`, line-height 1.15, letter-spacing -0.02em): hero headline only.
- **Headline/H2** (600, `clamp(1.5rem, 1.2vw + 1.1rem, 2rem)`, line-height 1.15): section titles ("Скачать", "Три способа...", etc).
- **Title/H3** (600, 1.05rem): card titles inside `.how-card`.
- **Body** (400, 1rem, line-height 1.6, color Text Muted, max-width 62ch): paragraph copy.
- **Label/Mono** (500, 0.75rem, letter-spacing 0.06em, uppercase-by-convention): `#lang-toggle` pill only — the sole place Plex Mono appears in the UI, marking it as a control rather than content.

### Named Rules
**The No-Kicker Rule.** Section and card headings are never preceded by an eyebrow/kicker label. A kicker treatment was built and removed during this redesign for violating the craft floor; it is a defect the build once carried, not a system element — do not reintroduce it on future surfaces.

## Layout

Two container widths, both centered: `.wrap` at `max-width: 1180px` for standard sections, `.wrap--narrow` at `640px` for single-column, form-like sections (Download, Guide, Support, Feedback). Side padding is `2rem` desktop, `1.25rem` at ≤640px.

The hero is the only two-column section: `grid-template-columns: minmax(0,1.2fr) minmax(0,0.8fr)` (copy left, screenshot right), collapsing to a single column below 900px with the screenshot reordered above the copy (`order: -1`). The "how it works" section is a 3-column grid (`.how-grid`) collapsing to 1 column below 900px.

Section rhythm: `4rem 2rem` vertical padding on desktop sections (`2.75rem 1.25rem` on mobile), each non-hero section separated by a 1px `border-top` rather than a background-color change or a shadow. The hero itself gets more room: `6rem 2rem 5.5rem` desktop, `3.5rem 1.25rem 3rem` mobile, per the direction contract's "generous top padding" instruction.

## Elevation & Depth

Flat by design — no box-shadows anywhere in the stylesheet. Depth is conveyed by a two-step tonal ladder (Ground → Elevated Surface) plus 1px hairline borders, not by shadow or blur (the sticky header uses `backdrop-filter: blur(10px)` for legibility over scrolling content, which is a translucency effect, not a shadow).

### Named Rules
**The Flat-Ladder Rule.** Elevation is a background-color step (Ground → Elevated Surface) plus a 1px border, never a `box-shadow`. This system carries no hard-offset shadow of any kind — not even the neobrutalist kind — because the world is a restrained dev-tool page, not a neobrutalist one.

## Shapes

Corner radius scales in three small steps off the `8px` base: `8px` (`--radius`) for buttons, form controls, and images inside frames; `12px` (`--radius + 4px`) for `.panel` and `.how-card`; `14px` (`--radius + 6px`) for the hero screenshot frame. The language toggle pill uses `999px` (full pill). Borders are always `1px solid`, stepping from `--border` to `--border-strong` only on hover — never a border-width or color-hue change.

## Components

### Buttons
- **Shape:** 8px radius (`--radius`), padding `0.8rem 1.6rem`.
- **Primary (`.cta`):** background Signal Orange, text Accent Ink, weight 600. Hover lightens to Signal Orange Hover plus a 1px lift (`translateY(-1px)`); active returns to rest position.
- **Ghost (`.cta-ghost`):** transparent background, Text-colored label, 1px Hairline Border. Hover fills to Elevated Surface and the border turns Signal Orange — the ghost variant's only accent contact.

### Cards / Containers
- **Panel (`.panel`):** the download and feedback-form container. Elevated Surface background, 1px Hairline Border, 12px radius, `1.75rem` padding (`1.25rem` mobile).
- **How-card (`.how-card`):** Elevated Surface background, 1px Hairline Border (steps to Border Strong on hover), 12px radius, `1.25rem` padding. Each card's `<figure>` is its own nested frame: Ground background, 1px Hairline Border, 8px radius — this is the "plain bordered image frame" the direction contract calls for; there is no device-chrome mockup anywhere on the page.
- **Hero shot frame (`.hero-shot`):** same plain-frame pattern at the larger 14px radius, `1.75rem` padding, holding `hero-shelf.png` uncropped.

### Inputs / Fields
- **Style:** Ground background, 1px Hairline Border, 8px radius, inherited font. Native `<select>` uses a custom SVG chevron in Text-Muted, no native OS arrow.
- **Focus/Hover:** border shifts to Signal Orange on hover; `:focus-visible` gets a 2px Signal Orange outline with 2px offset and 4px corner rounding — this is the page's one global focus treatment, applied uniformly, not per-component.
- **Disabled:** 55% opacity, hover suppressed (submit button while pending).

### Navigation
- Sticky header, Ground at 82% opacity with `backdrop-filter: blur(10px)`, 1px bottom border. Wordmark is "Blender" in Text plus "Shelf" in Signal Orange (`.brand-accent`) — the accent's other committed use besides CTAs. Language toggle is a pill-shaped ghost control in Plex Mono, the only mono-labeled UI chrome on the page.

### Bilingual content mechanism (signature pattern)
Every translatable element carries `data-ru`/`data-en` (plus `data-href-ru`/`data-href-en` and `data-src-ru`/`data-src-en` for links and images) holding both language strings inline in the markup; a toggle swaps the active language across the whole document. This is a structural convention, not a visual one, but it constrains the visual system: no layout may assume one language's string length, since either language can be live in either slot. Cards, buttons, and headings size to content, not to a fixed pixel width, for this reason.

## Do's and Don'ts

### Do:
- **Do** keep the accent to CTA / wordmark-accent / focus-ring / selection moments only (The One Accent Rule).
- **Do** use IBM Plex Sans for all UI text and IBM Plex Mono only for the language-toggle control, to keep the mono face legible as "this is a control."
- **Do** frame every product screenshot in a plain 1px-bordered box (`.hero-shot`, `.how-card figure`) at Ground or Elevated Surface background — never a fake browser/device chrome.
- **Do** step elevation with background-color + border only (Ground → Elevated Surface → Border-Strow on hover); never introduce a box-shadow.
- **Do** carry `data-ru`/`data-en` (and the `-href-`/`-src-` variants) on any new translatable element; do not hardcode a single-language string on new surfaces.

### Don't:
- **Don't** add a kicker/eyebrow label above any heading — this was built, then removed for violating the craft floor's explicit ban; it is not a system element to reintroduce.
- **Don't** add gradient text or a gradient fill anywhere; none exists in the shipped system and the direction contract calls for typographic hierarchy and whitespace to carry the design, not decorative gradients.
- **Don't** add hard-offset/neobrutalist shadows or any `box-shadow`; this is a flat-ladder system, not a neobrutalist one.
- **Don't** add a second saturated accent color or use the accent as a background fill outside CTA/wordmark contexts.
- **Don't** consume `--bg-elevated-2` for a new "third surface" without a real nested-elevation need — it's currently an unused reserved token, not an established third step.
