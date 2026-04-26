# Phase 08 — UX parity polish (toasts, empty states, keyboard, focus, About)

## Context Links
- Plan: [plan.md](plan.md)
- Source: `gui/main_window.py` (menu, About dialog), `gui/icons.py`, `gui/download_table.py` (status text patterns), Tier-1 GUI plan `plans/260426-1426-tier1-gui-modernization/` (semantic tokens, spacing already ported)
- Phase 07: tabs functional

## Overview
- **Priority:** Medium
- **Status:** pending
- **Effort:** 1.5d
- Close UX gaps after phase 07: error toasts, empty states, keyboard shortcuts, focus rings, About dialog, app menu, drag-drop affordances.

## Key Insights
- PySide6 used `QStatusBar` + `QMessageBox.about` — replicate as a status bar (already in shell) + a Svelte modal.
- Tier-1 plan (already shipped) defined semantic tokens & spacing — reuse directly in Svelte components.
- Tauri 2's app menu plugin is optional; for v2.0 a simple in-app dropdown is sufficient.

## Requirements
- Toast notifications for: download finished, download failed, history removed, settings saved, errors.
- Empty states: "No downloads yet — paste a URL or drop a `.txt`", "No videos in history", "No channel results".
- Keyboard shortcuts: `Ctrl+V` paste URL into Download input; `Ctrl+L` focus URL bar; `Ctrl+I` import; `Ctrl+E` export; `Ctrl+,` open Settings; `Esc` cancel current listing/active download focus.
- Focus rings visible on tab nav buttons + form controls.
- About modal: version, repo link, license note, "Powered by yt-dlp".
- Loading skeletons: progress shimmer for History fetch, channel listing.
- Persistent window position/size (already part of AppConfig; wire on Tauri close event).

## Architecture

```
src/lib/components/
├── Toast.svelte                  one toast item
├── ToastHost.svelte              fixed-position container; subscribes to toasts store
├── EmptyState.svelte             icon + message, used everywhere a list can be empty
├── AboutModal.svelte             version + credits
├── KbdShortcut.svelte            <kbd>Ctrl</kbd>+<kbd>V</kbd>
└── Skeleton.svelte               shimmer block
src/lib/stores/
└── toasts.ts                     writable<Toast[]>; push/dismiss helpers
src/lib/keyboard.ts               registerShortcuts(): attaches global handlers, returns unsubscribe
```

### Toast store
```ts
type Toast = { id: string; kind: 'success'|'error'|'info'|'warning'; message: string; durationMs?: number };
export const toasts = writable<Toast[]>([]);
export function pushToast(t: Omit<Toast, 'id'>): void { ... }
```

### Wiring map
| Event | Toast | Source |
|-------|-------|--------|
| `ProgressEvent.finished` | success: "Downloaded: {title}" | Download tab |
| `ProgressEvent.failed`   | error: "{title or url}: {kind}" | Download tab |
| `ProgressEvent.cancelled`| info: "Cancelled: {title}" | Download tab |
| `history:changed` after remove | success: "Removed from history" | History tab |
| Settings save | success: "Settings saved" (debounced) | Settings tab |
| Export complete | success: "Exported {count} URLs to {path}" | Download tab |
| Import error | error: parse failure | Download tab |
| Channel listing error | error: yt-dlp message | Channel tab |

## Related Code Files

### Create
- `src/lib/components/{Toast,ToastHost,EmptyState,AboutModal,KbdShortcut,Skeleton}.svelte`
- `src/lib/stores/toasts.ts`
- `src/lib/keyboard.ts`
- `src/lib/icons.ts` (lucide-svelte map; replaces qtawesome `mdi6.*` calls)

### Update
- `src/routes/+layout.svelte`: mount `<ToastHost />` and `registerShortcuts()` in `onMount`.
- All tab routes: replace ad-hoc errors with `pushToast({kind:'error', message})`.
- All list components: use `<EmptyState />` when result set is zero.

### Read for context
- `gui/icons.py` (24 LOC) — icon helper. Map `mdi6.exit-to-app` etc. to `lucide-svelte` equivalents.
- `gui/main_window.py:262-270` — About dialog content.

### Cargo deps
None new.

### Frontend deps
```
pnpm add lucide-svelte
```

## Implementation Steps

### Step 1 — Toasts
1. Implement store + `pushToast` with auto-dismiss (default 4s, errors 8s).
2. `ToastHost` renders a stack in the bottom-right corner; respects safe-area; max 5 visible (overflow drops oldest).
3. Wire all event sources from the table above.
4. Animate in/out via CSS transitions.

### Step 2 — Empty states
1. `EmptyState` accepts `icon`, `title`, `description`, optional CTA button.
2. Used in Download (no rows), Channel (no results), History (no records or filtered to zero).

### Step 3 — Keyboard shortcuts
1. `keyboard.ts::registerShortcuts()` attaches `keydown` to `window`. Map (`Ctrl/Cmd + key`):
   - `L` → focus URL bar (DOM ref via `document.getElementById('url-input')`).
   - `V` → if Download tab + clipboard text is a valid URL → push to input.
   - `I` → trigger Import.
   - `E` → trigger Export.
   - `,` → `goto('/settings')`.
   - `Esc` → context-aware: cancel active listing if Channel tab; clear focus otherwise.
2. Return cleanup fn.

### Step 4 — About modal
1. `AboutModal.svelte`: shows version (read from package.json via `import.meta.env.VITE_APP_VERSION`), "Powered by yt-dlp", license: MIT, repo link.
2. Trigger from a "?" button in TabNav header (top-right).

### Step 5 — Window geometry persistence
1. `+layout.svelte` `onMount`: `getCurrent().onCloseRequested(async () => { saveGeometry(); })`.
2. `saveGeometry()` reads `getCurrent().outerSize()` + `outerPosition()`, calls `setEngineConfig({ window_width, window_height, window_x, window_y })`.
3. On startup, BE applies saved geometry via `Window::set_size` + `Window::set_position` in `setup()`.

### Step 6 — Focus ring + a11y
1. Add `:focus-visible` outlines via Tailwind `focus-visible:ring-2 focus-visible:ring-[var(--color-accent-default)]`.
2. ARIA labels on icon-only buttons (Cancel, Retry).
3. Tab order check via dev tools.

### Step 7 — Loading skeletons
1. History list shows 5 skeleton rows during initial fetch.
2. Channel listing shows 3 rows during enumeration.

## Todo
- [ ] Toasts wired for 8 event types
- [ ] Empty states in 3 lists
- [ ] 6 keyboard shortcuts working
- [ ] About modal opens and shows current version
- [ ] Window geometry persists across restart
- [ ] Focus rings visible on all interactive elements
- [ ] Skeletons appear during loads
- [ ] No console warnings

## Success Criteria
- Manual smoke covers every UX trigger above.
- App passes a basic accessibility eyeball: keyboard-only nav reaches all controls; screen reader announces button labels.

## Risk Assessment
- **Clipboard read on `Ctrl+V` hits permission prompt on some OSes.** Use the clipboard plugin's `readText()` which Tauri permits per ACL.
- **Toast spam on large batch (50 URLs done at once).** Coalesce: show one summary toast "Downloaded N videos" if more than 3 finishes in 2s.
- **Window geometry on multi-monitor.** Validate stored x/y still maps to a connected screen; fallback to centered.

## Security
- Clipboard content sanitized: max length 8 KB; URL must pass `validate_url` before auto-paste into input.

## Next Steps
- Phase 09 builds the production installer.
