---
name: accessibility-review
description: Accessibility checklist for the dashboard — keyboard, contrast, semantics, charts, motion. Use when reviewing or changing interactive UI.
---
# Accessibility review

- Landmarks: skip link, `nav[aria-label=Main]`, one `main#main`, one h1 per page, headings in order.
- Keyboard: everything reachable by Tab in visual order; `:focus-visible` ring uses `--ring` (3:1 against both themes); drawer traps and restores focus; trace span list is a listbox with arrow-key selection.
- Contrast: body text 4.5:1, large 3:1, in BOTH themes. Faint text (`--faint`) is only for non-essential captions and must still pass 4.5:1 on `--bg`/`--panel`. Check badges (tinted bg + text).
- Meaning without colour: verdicts always carry words ("regression", "pass"); deltas carry a sign.
- Tables: real `<table>`, `<th scope>`, `aria-sort` on sortable headers, captions/labels, horizontal scroll inside a focusable-safe wrapper.
- Charts: `figure` + `aria-label` summarising numbers, with a table equivalent.
- Motion: no non-essential animation; `prefers-reduced-motion` disables skeleton shimmer and smooth scroll.
- Forms/annotation: labels bound to inputs, blind-annotation view never leaks labels.
- Errors/loading: `role=status`/`alert` on async states, distinct error kinds.
Run: Playwright smoke + `visual-qa` + manual Tab pass; a read-only reviewer agent should check contrast values from `globals.css`.
