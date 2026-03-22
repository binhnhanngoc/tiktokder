---
title: "TikTok Batch Video Downloader"
description: "Python CLI to batch-download TikTok videos without watermark using yt-dlp"
status: complete
priority: P2
effort: 2h
tags: [python, cli, feature]
created: 2026-03-21
completed: 2026-03-21
---

# TikTok Batch Video Downloader

## Overview

Python CLI script to batch-download TikTok videos without watermark. Supports single URL, batch file input, and user profile scraping. Uses yt-dlp as core engine.

## Context

- Brainstorm: [brainstorm report](../reports/brainstorm-260321-1834-tiktok-batch-downloader.md)

## Architecture

```
tiktokder/
├── main.py              # CLI entry point (argparse)
├── downloader.py        # yt-dlp wrapper, download logic
├── url_parser.py        # Parse/validate TikTok URLs, read batch files
├── requirements.txt     # yt-dlp, rich
└── downloads/           # Default output directory
```

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Project setup | Complete | 15m | [phase-01](./phase-01-project-setup.md) |
| 2 | Core implementation | Complete | 1h | [phase-02](./phase-02-core-implementation.md) |
| 3 | Testing & validation | Complete | 45m | [phase-03](./phase-03-testing.md) |

## Dependencies

- Python 3.8+
- `yt-dlp` — core download engine
- `rich` — progress display
