# Phase 06 — SvelteKit UI shell (layout, theme, design tokens, IPC plumbing)

## Context Links
- Plan: [plan.md](plan.md)
- Source: `gui/main_window.py`, `gui/theme.py`, `gui/tokens.py`, `gui/spacing.py`
- Phase 01: SvelteKit scaffold

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 1.5d
- Build the app shell: tab layout, theme provider with system/light/dark, design tokens via CSS variables (port `gui/tokens.py`), spacing scale, IPC wrappers, store skeletons. No tab content yet (phase 07).

## Key Insights
- Tailwind v4 supports CSS variables natively → semantic tokens become `--color-bg-canvas` etc., consumed via `bg-[var(--color-bg-canvas)]` or `theme()` utility classes.
- Theme detection: `window.matchMedia('(prefers-color-scheme: dark)')` for system mode + Tauri 2's `getCurrent().theme()` event for OS-level changes.
- SvelteKit prerendered single-page mode with hash routing keeps everything offline-capable.

## Requirements
- 4-tab top nav: Download / Channel / History / Settings.
- Theme toggle in Settings tab (System / Light / Dark) — persists to AppConfig.
- Design tokens (15 keys × 2 palettes) injected as CSS vars; flip on theme change.
- IPC wrappers (`src/lib/ipc.ts`) for every command from phases 03/04/05.
- Stores for: settings, theme, downloads (queue + progress map), history list, channel listing state.
- Status bar component (footer): "Ready" / "Downloaded N/M" / "All complete".
- App icon visible in window title bar.

## Architecture

```
src/
├── app.html                                       <html data-theme="..."> + minimal head
├── app.css                                        @import "tailwindcss"; + token CSS vars
├── lib/
│   ├── ipc.ts                                     invoke + event listeners + Channel consumers
│   ├── tokens.ts                                  LIGHT/DARK palettes (port of gui/tokens.py)
│   ├── spacing.ts                                 XS=4 ... XXXL=48 (port of gui/spacing.py)
│   ├── stores/
│   │   ├── settings.ts                            writable<AppConfig>
│   │   ├── theme.ts                               'system' | 'light' | 'dark' + applyTheme()
│   │   ├── downloads.ts                           Map<url, DownloadRow> + queue counters
│   │   ├── history.ts                             paged list + filter state
│   │   └── channel.ts                             current listing state
│   └── components/
│       ├── TabNav.svelte                          top tab bar
│       ├── StatusBar.svelte                       bottom footer
│       └── ThemeProvider.svelte                   no-render component, applies CSS vars on store change
└── routes/
    ├── +layout.ts                                 prerender=true; ssr=false
    ├── +layout.svelte                             ThemeProvider + TabNav + <slot/> + StatusBar
    ├── +page.svelte                               Download tab placeholder
    ├── channel/+page.svelte                       Channel tab placeholder
    ├── history/+page.svelte                       History tab placeholder
    └── settings/+page.svelte                      Settings tab — theme toggle + output dir picker (live in phase 07)
```

### Token mapping
`src/lib/tokens.ts` exports two records identical to Python:
```ts
export const LIGHT = { 'bg.canvas': '#FFFFFF', 'bg.surface': '#F7F8FA', /* ...15 keys */ };
export const DARK  = { 'bg.canvas': '#0F1115', /* ... */ };
```

`ThemeProvider.svelte` watches the theme store and writes them as CSS vars on `:root`:
```ts
$: applyVars(mode === 'dark' ? DARK : LIGHT);
function applyVars(palette: Record<string, string>) {
    for (const [k, v] of Object.entries(palette)) {
        document.documentElement.style.setProperty(`--color-${k.replace('.', '-')}`, v);
    }
}
```

Tailwind utilities reference them: `<div class="bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)]">`.

### IPC wrapper sketch (`src/lib/ipc.ts`)
```ts
import { invoke, Channel } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

export type ProgressEvent =
  | { type: 'started'; url: string }
  | { type: 'progress'; url: string; downloaded_bytes: number; total_bytes: number | null; speed: number | null; eta: number | null; percent: number }
  | { type: 'finished'; url: string; video_id: string | null; title: string | null; file_path: string | null; size_bytes: number | null }
  | { type: 'failed'; url: string; kind: string; message: string }
  | { type: 'cancelled'; url: string }
  | { type: 'skipped'; url: string; video_id: string; reason: string };

export async function addUrls(urls: string[], force = false, onEvent: (e: ProgressEvent) => void): Promise<void> {
    const channel = new Channel<ProgressEvent>();
    channel.onmessage = onEvent;
    await invoke('add_urls', { urls, force, onEvent: channel });
}

export const cancelUrl   = (url: string) => invoke<void>('cancel_url', { url });
export const cancelAll   = () => invoke<void>('cancel_all');
export const setEngineConfig = (cfg: Partial<AppConfig>) => invoke<void>('set_engine_config', { cfg });
export const historyList = (filter: HistoryFilter) => invoke<HistoryRecord[]>('history_list', { filter });
export const historyRemove = (id: string) => invoke<void>('history_remove', { videoId: id });
export const listChannel = (url: string, onEvent: (e: ChannelEvent) => void) => {
    const ch = new Channel<ChannelEvent>();
    ch.onmessage = onEvent;
    return invoke<number>('list_channel', { url, onEvent: ch });
};
```

App-wide events:
```ts
listen<{ count: number }>('queue:changed', (e) => downloads.update(d => ({ ...d, queueCount: e.payload.count })));
listen<void>('all:finished', () => statusBar.set('All downloads complete'));
listen<void>('history:changed', () => history.refresh());
```

## Related Code Files

### Create
- `src/app.html`, `src/app.css`
- `src/lib/ipc.ts`, `src/lib/tokens.ts`, `src/lib/spacing.ts`
- `src/lib/stores/{settings,theme,downloads,history,channel}.ts`
- `src/lib/components/{TabNav,StatusBar,ThemeProvider}.svelte`
- `src/routes/+layout.{ts,svelte}`
- `src/routes/+page.svelte` (Download placeholder)
- `src/routes/channel/+page.svelte` (placeholder)
- `src/routes/history/+page.svelte` (placeholder)
- `src/routes/settings/+page.svelte` (theme toggle live; rest placeholder)

### Read for context
- `gui/main_window.py` (tab order, signal wiring patterns)
- `gui/tokens.py` (palette values — copy verbatim)
- `gui/theme.py` (ALLOWED_MODES, system follow semantics)

### Update
- `src-tauri/src/commands.rs` — add `get_config` / `set_config` for settings store hydration.

## Implementation Steps

### Step 1 — Tokens + Tailwind
1. Port `LIGHT` and `DARK` records to `src/lib/tokens.ts`.
2. Apply CSS-var-based scheme (above).
3. `app.css`:
   ```css
   @import "tailwindcss";
   :root { color-scheme: light; }
   :root[data-theme="dark"] { color-scheme: dark; }
   body { background: var(--color-bg-canvas); color: var(--color-text-primary); }
   ```

### Step 2 — Theme store + provider
1. `theme.ts`: `writable<'system'|'light'|'dark'>`, plus a derived `effectiveMode` that follows OS in system mode.
2. `ThemeProvider.svelte`: subscribes to `effectiveMode`, applies CSS vars + sets `data-theme` attribute on `<html>`.
3. Bootstrap on layout mount: read `getConfig().theme_mode`, set store, attach a media-query listener for system mode + Tauri's `WebviewWindow.onThemeChanged()`.

### Step 3 — Tab nav + status bar
1. `TabNav.svelte`: 4 buttons → `goto('/')`, `goto('/channel')`, etc. Active state styled via `$page.url.pathname`.
2. `StatusBar.svelte`: subscribes to `downloads` store; renders Ready / X/Y / All complete.
3. `+layout.svelte`: vertical flex (tabnav, slot, statusbar).

### Step 4 — IPC plumbing
1. Implement all wrappers in `ipc.ts` (signatures from above).
2. Wire app-wide listeners (`listen`) once in `+layout.svelte` `onMount`. Tear down in `onDestroy`.

### Step 5 — Settings stub (theme toggle live)
1. Toggle radio: System / Light / Dark.
2. On change → update store + `setEngineConfig({ theme_mode })`.
3. Rest of Settings is placeholder (full form in phase 07).

### Step 6 — Smoke
1. `pnpm tauri dev` opens the shell with all 4 tabs navigable; theme toggle flips light/dark instantly.

## Todo
- [ ] CSS-var tokens applied; light/dark visibly differs
- [ ] Theme toggle persists across restart
- [ ] All 4 tab routes navigable; active styling correct
- [ ] StatusBar reactive to downloads store
- [ ] IPC wrappers TypeScript-clean; no `any` leaks
- [ ] Layout responsive at 720×480 minimum

## Success Criteria
- Run `pnpm tauri dev` → app opens, can switch tabs, can flip theme. Restart → theme remembered.
- No console errors on startup.

## Risk Assessment
- **Tailwind v4 SSR friction.** Disabled SSR for the app (`ssr=false` + `prerender`). No issue.
- **Tauri theme event API drift.** Stick to `matchMedia` first; Tauri's API is a bonus.
- **Store hydration race on cold start.** Layout `onMount` awaits `get_config` before rendering tabs to avoid theme flash.

## Security
- No remote URLs in `app.html`. CSP tightening deferred to phase 09 — set strict CSP that allows only `tauri:` and `data:` for fonts/images.

## Next Steps
- Phase 07 fills in the four tab routes with feature parity.
