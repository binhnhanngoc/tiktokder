"""PyInstaller runtime hook: point Playwright at the bundled Chromium cache.

The browser binaries live next to the frozen app under `ms-playwright/`
(see tiktokder.spec). Setting PLAYWRIGHT_BROWSERS_PATH before any
`playwright` import ensures `p.chromium.launch()` resolves to the
bundled binary instead of trying to download into a user-writable cache.
"""

import os
import sys

if hasattr(sys, "_MEIPASS"):
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(sys._MEIPASS, "ms-playwright"),
    )
