"""HTML content for HelpDialog tabs.

Pure data module — kept separate from `help_dialog.py` so the dialog widget
stays small. Each constant is a self-contained HTML fragment rendered in a
``QTextBrowser``. External ``https://`` anchors are routed to the system
browser by the dialog.
"""

from __future__ import annotations

from version import __version__

# Stable tab ids — referenced from the menu so wiring survives tab reorders.
TAB_GETTING_STARTED = "getting-started"
TAB_COOKIES_EXPORT = "cookies-export"
TAB_COOKIES_CONFIGURE = "cookies-configure"
TAB_CHANNELS_LIBRARY = "channels-library"
TAB_TROUBLESHOOTING = "troubleshooting"
TAB_SHORTCUTS = "shortcuts"
TAB_ABOUT = "about"


_GETTING_STARTED_HTML = """
<h2>Getting Started</h2>
<p>TikTokDer batch-downloads videos from TikTok and Facebook without
watermarks. Two interfaces share the same engine and history:</p>
<ul>
  <li><b>GUI</b> &mdash; <code>python app.py</code></li>
  <li><b>CLI</b> &mdash; <code>python main.py &lt;url&gt;</code> or
      <code>python main.py --batch urls.txt</code></li>
</ul>
<h3>Three top-level tabs</h3>
<ol>
  <li><b>TikTok</b> / <b>Facebook</b> &mdash; each platform has three
      sub-tabs: <i>Channels</i> (saved list + in-app browser), <i>Queue</i>
      (active downloads), <i>Library</i> (history + previews).</li>
  <li><b>Settings</b> &mdash; output folder, concurrency, cookies, default
      quality, theme, health checks.</li>
</ol>
<h3>Four ways to add downloads</h3>
<ul>
  <li>Paste a URL into the global URL bar at the top &rarr; press Enter.</li>
  <li>Drag a URL or a <code>.txt</code> batch file onto the URL bar or any
      platform tab.</li>
  <li>Open a channel/page in the <i>Channels</i> sub-tab &rarr; tick videos
      &rarr; <b>Download Selected</b>.</li>
  <li>Save a channel &rarr; right-click &rarr; <b>Download all new</b>
      (skips already-downloaded and pre-cutoff videos).</li>
</ul>
<h3>Output layout</h3>
<p>Defaults to <code>./downloads/{platform}/{uploader}/</code> with files
named <code>{title} [{short_id}].{ext}</code>. Duplicates are auto-skipped
via filesystem scan plus <code>data/history.json</code>.</p>
"""


_COOKIES_EXPORT_HTML = """
<h2>Exporting cookies</h2>
<p>Cookies let TikTokDer act as your logged-in browser session, which:</p>
<ul>
  <li><b>TikTok</b> &mdash; lifts anonymous rate limits on profile
      scrapes and downloads.</li>
  <li><b>Facebook</b> &mdash; lifts the 10-reel cap on anonymous page
      scraping and bypasses most login walls.</li>
</ul>
<h3>Recommended extension</h3>
<p><b>Get cookies.txt LOCALLY</b> &mdash; open-source, runs locally, exports
the Netscape format that yt-dlp expects.</p>
<ul>
  <li><a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc">Chrome / Edge Web Store</a></li>
  <li><a href="https://addons.mozilla.org/firefox/addon/cookies-txt/">Firefox Add-ons</a> (search "cookies.txt")</li>
</ul>
<h3>Steps</h3>
<ol>
  <li>Install the extension in your everyday browser.</li>
  <li>Log in to <code>tiktok.com</code> or <code>facebook.com</code> as
      normal.</li>
  <li>While on that domain, click the extension icon &rarr; <b>Export</b>
      (or <b>Export As &rarr; cookies.txt</b>).</li>
  <li>Save the file somewhere stable, e.g.
      <code>%USERPROFILE%\\tiktok-cookies.txt</code> or
      <code>~/fb-cookies.txt</code>. <b>Use one file per platform</b> &mdash;
      do not mix TikTok and Facebook cookies in the same file.</li>
</ol>
<p><b>Privacy.</b> The exported file contains active session tokens. Treat
it like a password &mdash; don't share it, don't commit it to git, and
re-export if you suspect it leaked.</p>
<p><b>Expiry.</b> Cookies expire on the platform's own schedule (typically
days to weeks). If downloads start failing with login/captcha errors,
re-export.</p>
"""


_COOKIES_CONFIGURE_HTML = """
<h2>Configuring cookies in TikTokDer</h2>
<p>Open the <b>Settings</b> tab.</p>
<h3>TikTok section</h3>
<ul>
  <li><b>Cookie Browser</b> &mdash; pick <code>chrome</code>,
      <code>firefox</code>, or <code>edge</code>. yt-dlp reads cookies
      directly from your browser profile. Easiest option, but requires the
      browser to be installed locally and not exclusively locked by
      another process.</li>
  <li><b>Cookies File</b> &mdash; path to a Netscape <code>cookies.txt</code>
      (see <i>Cookies &mdash; Export</i>). <b>Overrides Cookie Browser
      when set.</b> Use this on headless boxes, in CI, or when your
      browser is otherwise locked.</li>
</ul>
<h3>Facebook section</h3>
<ul>
  <li><b>Cookies File</b> &mdash; Netscape <code>cookies.txt</code>. There
      is no Cookie Browser option for Facebook because Playwright drives
      the scrape and needs the file directly.</li>
  <li><b>Default Max Scrolls</b> &mdash; how many times the headless
      browser scrolls a page during a fetch. Higher = more videos
      discovered, but slower and more visible to rate-limit heuristics.</li>
</ul>
<h3>What changes after cookies are set?</h3>
<ul>
  <li>Saved-channel <b>Refresh</b> returns more videos.</li>
  <li><b>Download all new</b> picks up older items previously hidden behind
      login walls.</li>
  <li>Anonymous rate-limit failures drop to near zero.</li>
</ul>
<p><b>Settings auto-save</b> on every change and propagate live to the
engine and browser panels &mdash; no restart needed.</p>
"""


_CHANNELS_LIBRARY_HTML = """
<h2>Channels &amp; Library</h2>
<h3>Saving channels</h3>
<ul>
  <li>In the <i>Channels</i> sub-tab, paste a channel/page URL into the
      browser panel, fetch the video list, then click
      <b>Save channel</b>.</li>
  <li>Optional <b>nickname</b> renames ugly URLs (e.g.
      <code>profile.php?id=...</code>) to anything readable.</li>
  <li>Right-click a saved row for <b>Refresh</b>,
      <b>Download all new</b>, <b>Rename + notes</b>, <b>Edit URL</b>,
      <b>Star</b>, <b>Remove</b>.</li>
</ul>
<h3>Browse filters</h3>
<ul>
  <li>Search box, quality dropdown, From/To date range, sortable
      headers.</li>
  <li><b>Downloaded filter</b> &mdash; <i>All</i>, <i>New only</i>, or
      <i>Downloaded only</i>. The <b>&#10003;</b> column shows download
      status; hover for the timestamp tooltip. The selection persists per
      platform across relaunches.</li>
  <li><b>Select All</b> / <b>Download Selected</b> respect the active
      filter &mdash; hidden rows are never queued by accident.</li>
</ul>
<h3>Library 3-pane view</h3>
<ul>
  <li><b>Left</b> &mdash; uploader sidebar; <b>&#9733;</b> marks saved
      channels.</li>
  <li><b>Middle</b> &mdash; sortable table (Thumbnail &middot; Title
      &middot; Quality &middot; Size &middot; Date &middot; Status).
      Filters: search, quality, date range, size, Available/Missing.</li>
  <li><b>Right</b> &mdash; preview pane: large thumbnail, metadata, full
      description.</li>
  <li>Right-click a row: <b>Open file</b>, <b>Open folder</b>,
      <b>Re-download</b>, <b>Copy URL</b>, <b>Remove</b>.</li>
</ul>
"""


_TROUBLESHOOTING_HTML = """
<h2>Troubleshooting</h2>
<h3>Rate limits / 429 errors</h3>
<ul>
  <li>Settings &rarr; raise <b>Delay</b> to <code>2.0</code>&ndash;<code>3.0</code>s.</li>
  <li>Lower <b>Concurrent Downloads</b> to <code>1</code>&ndash;<code>2</code>.</li>
  <li>Wait 1&ndash;2 hours, then retry. Persistent block? Configure cookies
      (see <i>Cookies &mdash; Configure</i>).</li>
</ul>
<h3>Facebook login wall</h3>
<p>Detected fast and surfaced as a row error. Add a Facebook
<code>cookies.txt</code> from a logged-in session to bypass.</p>
<h3>Missing ffmpeg</h3>
<p>Most non-merge downloads still succeed, but quality presets like
<i>Best</i> and <i>Audio only</i> need ffmpeg on PATH. Install via
<a href="https://ffmpeg.org/download.html">ffmpeg.org</a> or your package
manager.</p>
<h3>Duplicate detection</h3>
<ul>
  <li>Already-downloaded videos are skipped via filesystem scan plus
      <code>data/history.json</code>.</li>
  <li>To re-download, right-click a Queue or Library row &rarr;
      <b>Force Download</b>, or remove the existing file first.</li>
</ul>
<h3>Health pill (status bar)</h3>
<p>Click the colored pill in the status bar (or open Settings &rarr;
Health) for detected issues: stale cookies, missing ffmpeg, broken saved
channels, yt-dlp updates available. Each issue exposes a one-click
<b>Fix</b> action.</p>
<h3>Failed downloads</h3>
<p>The Queue sub-tab shows per-row error text. <b>Retry</b> single rows
from the right-click menu; <b>Retry Failed</b> on the toolbar re-queues
every Failed row at once.</p>
"""


_SHORTCUTS_HTML = """
<h2>Keyboard shortcuts</h2>
<table cellspacing="6">
  <tr><td><b>F1</b></td><td>Open this Help dialog</td></tr>
  <tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
  <tr><td><b>Ctrl+F</b></td><td>Focus the Library search box</td></tr>
  <tr><td><b>Tab</b></td><td>Switch top-level tabs (TikTok / Facebook / Settings)</td></tr>
  <tr><td><b>Enter</b></td><td>(in URL bar) Submit URL</td></tr>
</table>
<h3>Mouse</h3>
<ul>
  <li><b>Right-click</b> &mdash; context menu on every table row
      (Channels, Queue, Library).</li>
  <li><b>Drag &amp; drop</b> &mdash; drop URLs or <code>.txt</code> files
      onto the URL bar or any platform tab.</li>
  <li><b>Click column header</b> &mdash; sort.</li>
</ul>
"""


def _about_html() -> str:
    return f"""
<h2>TikTokDer v{__version__}</h2>
<p>Batch video downloader for TikTok and Facebook.</p>
<h3>Powered by</h3>
<ul>
  <li><a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> &mdash; extraction</li>
  <li><a href="https://www.qt.io/qt-for-python">PySide6</a> &mdash; GUI</li>
  <li><a href="https://playwright.dev/python/">Playwright</a> &mdash; Facebook scrape</li>
  <li><a href="https://rich.readthedocs.io/">Rich</a> &mdash; CLI progress UI</li>
</ul>
<p><b>License:</b> MIT.</p>
<p><small>No watermarks, no API keys, no telemetry. Use responsibly and
respect each platform's terms of service.</small></p>
"""


def help_tabs() -> tuple[tuple[str, str, str], ...]:
    """Tab definitions in display order: ``(tab_id, label, html)``."""
    return (
        (TAB_GETTING_STARTED, "Getting Started", _GETTING_STARTED_HTML),
        (TAB_COOKIES_EXPORT, "Cookies — Export", _COOKIES_EXPORT_HTML),
        (TAB_COOKIES_CONFIGURE, "Cookies — Configure", _COOKIES_CONFIGURE_HTML),
        (TAB_CHANNELS_LIBRARY, "Channels & Library", _CHANNELS_LIBRARY_HTML),
        (TAB_TROUBLESHOOTING, "Troubleshooting", _TROUBLESHOOTING_HTML),
        (TAB_SHORTCUTS, "Shortcuts", _SHORTCUTS_HTML),
        (TAB_ABOUT, "About", _about_html()),
    )
