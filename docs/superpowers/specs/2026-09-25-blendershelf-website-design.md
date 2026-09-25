# BlenderShelf Website — Design Spec

**Date:** 2026-09-25
**Status:** Approved by owner, ready for implementation planning.

## Purpose

A public website for distributing the BlenderShelf Blender addon and supporting its users, replacing the current manual "here's a zip file" distribution. Three goals, in priority order:

1. Always offer the latest addon version, plus older versions matched to the user's Blender version (for when a future release drops support for an older Blender).
2. Collect user feedback (bugs, feature requests, questions) through a simple form, sorted into actionable categories without requiring an LLM conversation.
3. Accept donations to support the owner's future addon projects, covering both Russian-speaking and international audiences.

Plus: a short video guide (RU + EN) embedded on the site, and a bilingual (RU/EN) UI throughout.

**Owner context:** solo developer maintaining several side projects (BlenderShelf, MedBaza, Normal Tools, etc.). The site must require minimal ongoing maintenance and cost nothing to run. No existing website, domain, or BlenderShelf git repository exists yet — git itself is configured (`denis.ghome@gmail.com`) and a personal GitHub account is in use elsewhere (`vibecoding` repo under `IT-Garage-Community`).

## Scope decisions (confirmed with owner)

- One project, one spec, three feature areas (distribution, feedback, donations) — not decomposed into separate specs. Delivered in phases (see Phased Rollout).
- New repository on the owner's **personal** GitHub account (not an org), **public** (required so release assets are downloadable without authentication; source code review found nothing sensitive — only `"author": "DenisZakharov"` in `bl_info`, no secrets, no personal paths, no offensive content).
- Hosting: **GitHub Pages**, free subdomain (`<username>.github.io/blendershelf` or similar) — no purchased domain.
- Site is a **single-page landing page** with anchor-linked sections (Hero → Download → Guide → Feedback → Donate → Footer), not multiple `.html` pages.
- Feedback: a **simple structured form**, not an LLM chat dialogue — categorization is done via explicit form fields, not free-text classification.
- Feedback submission requires **no GitHub account** from the submitter, and must **not** route to the owner's personal email or require setting up a dedicated inbox.
- Donations: **both** a Russian-audience rail (Boosty) and an international rail (Ko-fi and/or GitHub Sponsors) — these are non-overlapping payment audiences (Boosty targets RU/CIS cards, SBP, YooMoney; Stripe/PayPal-based platforms don't accept Russian cards), so both are offered side by side, clearly labeled.

## Architecture

**Repository layout** (new public repo, e.g. `BlenderShelf`):
```
BlenderShelf/
  addon/              # current __init__.py and addon source (was BlenderShelf/)
  site/               # the website (GitHub Pages source)
    index.html        # single-page landing, bilingual via data-ru/data-en attributes
    versions.json      # compatibility manifest (see below)
  build_release.py     # adapted: packages zip + attaches to a GitHub Release
docs/                  # this spec and future ones
```

GitHub Pages serves from `site/` (exact branch/folder config decided at implementation time — no functional difference to the user).

### Version distribution

- Each addon release is published as a **GitHub Release**: tag = addon version (e.g. `v0.2.0`), with `BlenderShelf.zip` attached as a release asset.
- `versions.json` in the repo is a **manually maintained** compatibility manifest:
  ```json
  [
    { "addon_version": "0.2.0", "blender_min": "4.1.0", "blender_max": null, "url": "<release asset URL>" },
    { "addon_version": "0.1.0", "blender_min": "3.6.0", "blender_max": "4.0.9", "url": "<release asset URL>" }
  ]
  ```
  `blender_max: null` means "and all newer" (the current release). When a future release drops support for an old Blender version, the previous entry gets a `blender_max` cap and a new entry is added on top. No automation — updated by hand at each release, since releases are infrequent.
- Download section UI: a dropdown "My Blender version: [4.4 ▾]" populated from `versions.json`; selecting a version shows the matching addon build + download button. If no exact match exists (Blender version older/newer than anything listed), show the closest compatible version with an "unofficially compatible, use at your own risk" note.
- A secondary "show all versions" link lists every release for users who want to deliberately roll back.
- **Error handling:** if `versions.json` fails to load (network error, malformed JSON), show a fallback message ("Couldn't detect your version — download the latest here") linking directly to the latest GitHub Release.

### Feedback system

**Form fields:**
- Type (required, radio): Bug / Feature request / Question / Other
- Severity (conditional, only shown when Type = Bug): Blocks/crashes Blender / Feature doesn't work / Cosmetic-minor
- Blender version + BlenderShelf version (text, required for bugs, optional otherwise)
- Description (required, free text)
- Contact info (optional, only if the submitter wants a reply)

**Sorting principle (owner-designed, no LLM needed):** categorization is fully determined by the submitter's own explicit form choices, mapped directly to GitHub Issue labels — no keyword/AI classification required:
- `type:bug` / `type:feature` / `type:question` / `type:other` from the Type field
- `severity:critical` / `severity:major` / `severity:minor` from the Severity field (bugs only)
- Auto-generated issue title: `[Bug][critical] <first 60 chars of description>` (pattern varies by type/severity)

**Triage priority (a manual process for the owner, not automated):** critical bugs first, then major bugs, then feature requests reviewed in batches (matching the existing `FEEDBACK.md` practice), then questions answered/closed as time allows. No fix is ever applied automatically from a feedback submission — sorting only categorizes; the decision to act stays manual, consistent with the owner's existing standing rule for `FEEDBACK.md`.

**Technical implementation:** the form posts to a **Cloudflare Worker** (free tier) holding a GitHub Personal Access Token as a secret; the Worker creates a labeled GitHub Issue via the GitHub API. This lets submitters stay anonymous (no GitHub account, no email) while feedback lands directly in the repo's Issues, matching the owner's existing workflow. Spam mitigation: a honeypot field (hidden from humans, filled by bots) instead of a CAPTCHA, to keep the form frictionless.

**Error handling:** if the Worker/GitHub API call fails, show "Couldn't submit, please try again later" — no retry queue or offline storage; this is a low-stakes static site, not a critical service.

### Donations

- A "Support this project" section with two clearly separated, labeled blocks:
  - **For Russian-speaking users:** Boosty button/widget (one-off donation, optionally a subscription later).
  - **International:** Ko-fi (and/or GitHub Sponsors) for card/PayPal one-off donations.
- Both are external links/embedded buttons — no payment processing, no PCI scope, no custom donation tracking on the site (each platform has its own dashboard).

### Internationalization (RU/EN) and video guide

- Single HTML file per language pairing: elements carry `data-ru="..."` / `data-en="..."` attributes; a small JS toggle at the top of the page switches visible text, remembers the choice in `localStorage`. No server-side routing, no duplicated page files.
- **Two video guides** (RU and EN), each embedded via `<iframe>` (hosted on YouTube or similar — no self-hosted video, no bandwidth cost to the site). The language toggle swaps which iframe is shown/active alongside the text, using the same switching mechanism.
- The existing PDF guide is offered alongside the video as an alternative/companion download, also split RU/EN if a translated version exists.

## Phased Rollout

1. **Phase 1 (MVP):** landing page + Download section (Releases + `versions.json`) + video guide/PDF + language toggle. Shippable and shareable on its own.
2. **Phase 2:** feedback form + Cloudflare Worker → GitHub Issues integration.
3. **Phase 3:** donations section.

## Testing / Verification

No automated test framework — the site is small enough that a manual pre-release checklist suffices:
- Version dropdown resolves to the correct build for a selected Blender version.
- Feedback form actually creates a GitHub Issue with the expected labels (verified once per Worker deployment/change).
- Language toggle switches all content, including the active video embed.
- Boosty/Ko-fi links are live and correct.

## Explicitly out of scope (YAGNI)

- LLM-based feedback triage or conversation.
- Automated fixes generated from feedback.
- Self-hosted video.
- A purchased domain.
- A static site generator/build toolchain (plain HTML is sufficient at this scale).
- Donation tracking/analytics on the site itself.
- Automated `versions.json` generation from git tags (manual edit is fine given release frequency).
