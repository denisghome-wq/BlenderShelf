# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain static HTML/CSS/vanilla JS, no framework, no build step. Deployed to GitHub Pages from `site/`. A separate Cloudflare Worker handles the feedback-form submission (creates a GitHub Issue); nothing else is server-rendered.

## Users

Blender users looking for a floating, Maya-shelf-style button toolbar in the 3D viewport, plus an optional radial pie menu — hobbyists and freelancers up through production riggers/modellers who script their own tools and want one-click access to them. International audience, Russian and English treated as equally primary (the site is fully bilingual via a language toggle, not RU-first with EN as an afterthought).

## Product Purpose

Distribute and support the BlenderShelf Blender addon: let a visitor understand what it does, download the right build for their Blender version, learn to use it, give feedback, and optionally support development. Success is a visitor who downloads with confidence they picked the right version and knows the next step (install, watch the guide, or open the PDF).

## Positioning

A Maya-shelf-style floating toolbar + pie menu for Blender that deliberately stays simpler and friendlier than Pie Menu Editor (PME), the established but complex/power-user-oriented alternative in this space. No arbitrary scripting layer, no deep configuration surface — a compact button/pie-menu builder any user can pick up, not just PME power users.

## Operating Context

A visitor arrives (likely from a Blender community link, forum, or word of mouth), reads what the addon does, picks their Blender version from a dropdown to get the matching release download, optionally watches an embedded video guide or downloads a PDF guide, can leave a bug/feature/question via an in-page form (no GitHub account needed — it opens a GitHub Issue on their behalf through the Worker), and can optionally support the project via Boosty. All of this happens on one long-scroll page today; page order is negotiable for the redesign.

## Capabilities and Constraints

- Version-aware download: `versions.json` maps `addon_version` → `blender_min`/`blender_max`/release-asset URL; the page picks the closest compatible build for the visitor's selected Blender version and shows a risk warning when it's not an exact match.
- Bilingual RU/EN via a single toggle, driven by `data-ru`/`data-en` attributes on any element plus `data-href-ru`/`data-href-en` and `data-src-ru`/`data-src-en` variants — this mechanism must be preserved or cleanly re-implemented, not dropped.
- Feedback form posts to a Cloudflare Worker (bug/feature/question/other, severity, versions, optional contact) which opens a GitHub Issue; has a honeypot field for spam.
- Support section: a single Boosty link today (`https://boosty.to/gamedev_tut`); no Ko-fi yet (owner has none currently), leave room to add a second support link later without a redesign.
- No backend/database beyond the Worker; no user accounts; no analytics mentioned so far.
- Only one addon release exists today (0.1.0, Blender 4.1–5.x), so the version-picker UI currently always resolves to the same file — known low-value-for-now by the owner, kept for when a second release exists.

## Brand Commitments

- Name: **BlenderShelf**, wordmark today rendered as "Blender" + accent-colored "Shelf". No formal logo/mark beyond this text lockup.
- Repo/GitHub: `blendershelf/BlenderShelf`, addon author credited as "DenisZakharov".
- Boosty handle: `gamedev_tut`.
- Current visual world (dark near-black background, orange accent, Hanken Grotesk) is being explicitly discarded as evidence/anti-reference for this redesign — not a constraint to preserve.
- **2026-09-26 standing visual-direction choice:** offered a rolled/grounded design-world direction (technical-blueprint metaphor) plus alternates; owner explicitly chose the standing-exit "classic dark dev-tool landing" path instead, played straight, no metaphor/world-building. Craft bar named by the owner: **Linear, Raycast, and Vercel** — restrained near-black ground, one disciplined accent color, precise type hierarchy, plain bordered screenshots, no decorative flourish. This is now the standing default for future surfaces on this site unless the owner says otherwise.

## Evidence on Hand

Real product screenshots exist and should be used instead of any invented imagery:
- `guide/screenshots/` — 18 real in-Blender UI screenshots (shelf horizontal/vertical closeups, settings panels, pie menu, "Add to Shelf" context-menu flow, prefs panels, etc.), used today in the PDF guide.
- `guide/preview/` — 7 rendered PDF guide pages (`page_1.png`…`page_7.png`).
- No testimonials, user quotes, download counts, or star counts are available or to be shown — the owner explicitly declined fabricated or unverified social proof; if a number/quote isn't real and on hand, it doesn't appear on the page.

## Product Principles

1. Simple and approachable beats powerful and configurable — every design and copy choice should read as easier than PME, never as "another power-user tool."
2. Bilingual parity: RU and EN are both primary; neither reads as the translated afterthought of the other.
3. Show, don't claim: real screenshots/illustrations from the guide carry the proof burden; no invented metrics or quotes.
4. Get the visitor to a correct download with confidence, without over-indexing on the currently-moot version picker.
5. Static-site simplicity is a constraint, not a limitation to work around with unnecessary tooling.

## Accessibility & Inclusion

No specific standard mandated yet; no known accessibility requirement beyond ordinary web good practice (contrast, keyboard-usable form, readable type at normal zoom).
