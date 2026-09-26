---
version: 1
slug: "site-index-html"
primary_target: "site/index.html"
related_targets: []
---

## Scope

Full visual redesign of the single-page BlenderShelf marketing/distribution site (`site/index.html`, `site/assets/style.css`). Mode: Persuade. Section order and structure may change; existing functionality (version-matched download, bilingual RU/EN toggle, feedback form -> GitHub Issues Worker, Boosty support link) must be preserved and re-skinned, not rebuilt.

## Audience, job, action

International Blender users (RU/EN equally primary) evaluating whether to install a floating Maya-shelf-style toolbar + pie-menu addon. Job: understand the mechanism in seconds, trust it's simple (not another Pie Menu Editor-style power tool), download the build matching their Blender version, and know the next step (guide, feedback, or support).

## Proof / content

Real screenshots only, from `guide/screenshots/` (18 in-Blender UI captures) and `guide/preview/` (7 rendered guide pages). No invented testimonials, download counts, or star counts.

## Constraints

Static HTML/CSS/vanilla JS, no build step, GitHub Pages. Preserve the `data-ru`/`data-en` (+ `-href-`/`-src-` variants) translation mechanism. Preserve `versions.json`-driven download logic and the feedback Worker integration.

## Direction contract

**THESIS:** A precise, restrained dark developer-tool page — one disciplined accent color plus typographic hierarchy and whitespace do the persuading, not a themed metaphor. Refuses both the current muddy/generic dark-orange execution and any experimental world-building (a rolled blueprint-schematic direction was offered and declined in favor of this standing path).

**OWN-WORLD:** Warm-neutral near-black ground (not pure black), a single refined warm-amber-orange accent used at Committed weight (large CTA fields, glow accents, active states — not scattered chips) carrying 30-60% visual weight in its moments. IBM Plex Sans for all UI text (headings and body alike, variable weight for hierarchy) — chosen specifically because it renders Latin and Cyrillic as one coherent type family, solving the stated font complaint. Hairline 1px borders, radius-8 cards, no heavy shadows or decorative gradients. Real product screenshots shown in plain bordered frames (never fake device chrome).

**STORY:** Visitor understands in one glance this is a Blender viewport toolbar + pie-menu addon; believes it's simple and trustworthy rather than another complex power-tool; acts by downloading the build for their Blender version, watching the guide, or leaving feedback.

**FIRST VIEWPORT:** Generous top padding, a two-line bold headline, one-line muted subhead, a primary accent-colored CTA button, and a real screenshot (`12_shelf_hero_closeup.png`) in a bordered card beside the copy on desktop, below it on mobile — plain screenshot, Linear/Raycast convention, not an artificial device mockup.

**FORM:** Standing-exit / canon path (classic dark dev-tool landing, no world-building metaphor), explicitly chosen by the user over the rolled direction. Craft bar named by the user: Linear, Raycast, Vercel. Seed key `8ec5be48` (mode persuade); rolled assignment was index 6 of the model's own 7-candidate list (a technical-blueprint-schematic direction), declined by the user in favor of canon.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved decisions

- Exact section order (owner said reordering is fine; propose one in the build).
- Whether to add a second image-conversion/asset pipeline step for screenshots (none needed at current scale — plain PNGs served as-is).
