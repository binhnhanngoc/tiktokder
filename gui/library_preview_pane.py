"""Right-side preview pane for the Library tab.

Two stacked pages: a static thumbnail (selection preview) and an inline
``QMediaPlayer`` (double-click playback). The thumbnail uses ``QPixmapCache``
keyed with a ``large:`` prefix so the big preview isn't re-decoded on every
re-selection.

Player behavior (schema-v4-aware):
  - Resume from ``play_position_seconds`` when the saved offset is between
    5s and ``duration - 5s``.
  - Debounced position persistence: at most one disk write per 5 s while
    playing, plus a final write on stop / pause / source-change / closeEvent.
  - Codec failure → swap the video area for a "Open externally" fallback
    panel (uses ``open_path``); never crashes, never loops.
  - Keyboard (active only when the player page has focus): J/L = ±10 s,
    ←/→ = ±5 s, space/K = toggle play/pause.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QKeySequence, QPixmap, QPixmapCache, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import HISTORY_PATH, HistoryRecord
from gui._history_helpers import format_date, format_size, open_path
from gui.library_thumbnail_delegate import load_thumbnail_pixmap
from history_store import update_history_record_fields

PREVIEW_W, PREVIEW_H = 360, 200
_LARGE_CACHE_PREFIX = "large:"

# Persist position at most once every 5 s while playing. The timer is reset on
# every positionChanged tick, so disk only sees a write on the trailing edge.
_POSITION_PERSIST_MS = 5000

# Resume only inside this guard band — short clips and "watched-to-end" both
# fall outside, so the player starts at 0 instead of seeking past the end.
_RESUME_GUARD_SECONDS = 5.0

_AUDIO_ONLY_EXTS = {".m4a", ".mp3", ".aac", ".ogg", ".opus", ".flac", ".wav"}


def _is_audio_only(path: str | None) -> bool:
    """True when ``path`` ends with a known audio-only extension."""
    if not path:
        return False
    return Path(path).suffix.lower() in _AUDIO_ONLY_EXTS


def _format_ms(ms: int) -> str:
    """Render milliseconds as ``mm:ss`` (``-`` for negative/unset)."""
    if ms < 0:
        return "-"
    total = ms // 1000
    return f"{total // 60:02d}:{total % 60:02d}"


class LibraryPreviewPane(QWidget):
    """Detail pane: thumbnail/player stack + metadata + full description."""

    def __init__(self, placeholder: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        self._current_record: HistoryRecord | None = None
        self._playing_record: HistoryRecord | None = None
        self._pending_resume_seconds: float | None = None
        self._scrubber_user_dragging = False

        layout = QVBoxLayout(self)

        # ── stacked thumbnail ↔ player ───────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setFixedSize(PREVIEW_W, PREVIEW_H + 40)  # +transport bar
        self._thumb_page = self._build_thumb_page()
        self._player_page = self._build_player_page()
        self.stack.addWidget(self._thumb_page)
        self.stack.addWidget(self._player_page)
        layout.addWidget(self.stack, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── metadata form ───────────────────────────────────────────────
        self.title_label = QLabel("Select a video to see details")
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.uploader_label = QLabel("—")
        self.date_label = QLabel("—")
        self.quality_label = QLabel("—")
        self.size_label = QLabel("—")
        self.url_label = QLabel("—")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.url_label.setWordWrap(True)
        form.addRow("Uploader", self.uploader_label)
        form.addRow("Date", self.date_label)
        form.addRow("Quality", self.quality_label)
        form.addRow("Size", self.size_label)
        form.addRow("URL", self.url_label)
        layout.addLayout(form)

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.description.setPlaceholderText("(No description)")
        layout.addWidget(self.description, stretch=1)

        # ── player wiring ───────────────────────────────────────────────
        self.audio_output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self._video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_error_occurred)

        # Trailing-edge debounce for position persistence. Reset on every
        # positionChanged tick; only fires when playback is stable for 5 s.
        self._position_persist_timer = QTimer(self)
        self._position_persist_timer.setSingleShot(True)
        self._position_persist_timer.setInterval(_POSITION_PERSIST_MS)
        self._position_persist_timer.timeout.connect(self._persist_position)

        self._build_shortcuts()
        self.set_record(None)

    # ── build helpers ───────────────────────────────────────────────────

    def _build_thumb_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.thumb = QLabel()
        self.thumb.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("background:#1c1c1c; border-radius:4px;")
        layout.addWidget(self.thumb)
        layout.addStretch()
        return page

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        # focusPolicy needed so QShortcut(parent=page) keys arrive when the
        # user clicks into the player area (not the title/description below).
        page.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Video area + fallback panel sharing the same slot via a small stack.
        self._video_stack = QStackedWidget()
        self._video_stack.setFixedSize(PREVIEW_W, PREVIEW_H)

        self._video_widget = QVideoWidget()
        self._video_widget.setFixedSize(PREVIEW_W, PREVIEW_H)
        self._video_widget.setStyleSheet("background:#000; border-radius:4px;")

        self._fallback_panel = self._build_fallback_panel()

        self._video_stack.addWidget(self._video_widget)
        self._video_stack.addWidget(self._fallback_panel)
        layout.addWidget(self._video_stack)

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        self.play_btn = QPushButton("⏸")
        self.play_btn.setFixedWidth(30)
        self.play_btn.clicked.connect(self._toggle_play)
        transport.addWidget(self.play_btn)

        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 0)
        # sliderMoved fires only on user drag; valueChanged would echo
        # programmatic positionChanged updates and feedback-loop the seek.
        self.scrubber.sliderPressed.connect(self._on_scrubber_pressed)
        self.scrubber.sliderReleased.connect(self._on_scrubber_released)
        self.scrubber.sliderMoved.connect(self._on_scrubber_moved)
        transport.addWidget(self.scrubber, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        transport.addWidget(self.time_label)
        layout.addLayout(transport)

        return page

    def _build_fallback_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedSize(PREVIEW_W, PREVIEW_H)
        panel.setStyleSheet("background:#1c1c1c; border-radius:4px;")
        v = QVBoxLayout(panel)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg = QLabel("Can't play this format.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(msg)
        self._fallback_btn = QPushButton("Open externally")
        self._fallback_btn.clicked.connect(self._open_externally)
        v.addWidget(self._fallback_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return panel

    def _build_shortcuts(self) -> None:
        """J/K/L + space + arrows scoped to the player page only.

        Scoping to ``self._player_page`` (instead of ``self``) keeps these
        keys from hijacking input in the Library search box and other widgets.
        """
        bindings = (
            (Qt.Key.Key_Space, lambda: self._toggle_play()),
            (Qt.Key.Key_K, lambda: self._toggle_play()),
            (Qt.Key.Key_J, lambda: self._seek_relative(-10000)),
            (Qt.Key.Key_L, lambda: self._seek_relative(+10000)),
            (Qt.Key.Key_Left, lambda: self._seek_relative(-5000)),
            (Qt.Key.Key_Right, lambda: self._seek_relative(+5000)),
        )
        self._shortcuts = []
        for key, handler in bindings:
            sc = QShortcut(QKeySequence(key), self._player_page)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)
            self._shortcuts.append(sc)

    # ── public API ──────────────────────────────────────────────────────

    def set_record(self, rec: HistoryRecord | None) -> None:
        """Populate the pane from ``rec``, or reset it to the empty state.

        If a different record is currently playing, persist its position and
        stop the player before switching back to the thumbnail page.
        """
        if (
            self._playing_record is not None
            and (rec is None or rec.video_id != self._playing_record.video_id)
        ):
            self.stop_and_show_thumb()

        self._current_record = rec
        if rec is None:
            self.thumb.setPixmap(self._placeholder)
            self.title_label.setText("Select a video to see details")
            for lbl in (
                self.uploader_label,
                self.date_label,
                self.quality_label,
                self.size_label,
                self.url_label,
            ):
                lbl.setText("—")
            self.description.clear()
            return
        self.thumb.setPixmap(self._lookup(rec.thumbnail_path))
        self.title_label.setText(rec.title or "—")
        self.uploader_label.setText(rec.uploader or "—")
        self.date_label.setText(format_date(rec.downloaded_at))
        self.quality_label.setText(rec.quality or "—")
        self.size_label.setText(format_size(rec.size_bytes))
        self.url_label.setText(rec.url or "—")
        self.description.setPlainText(rec.description or "")

    def play(self, rec: HistoryRecord) -> None:
        """Switch to player page and start playback for ``rec``.

        File-missing → external-open fallback (no point loading a dead path).
        Audio-only → keep thumbnail visible behind the transport bar by hiding
        the (black) video widget; the audio output still routes correctly.
        Resume → stash the saved offset; the actual seek happens once Qt
        reports ``LoadedMedia`` (position is invalid before that).
        """
        if not rec or not rec.file_path:
            return
        path = rec.file_path
        if not Path(path).exists():
            # No point starting the player on a dead path.
            open_path(path)
            return

        # Different record currently playing → persist its outgoing position
        # before switching the source.
        if self._playing_record is not None and self._playing_record.video_id != rec.video_id:
            self._persist_position()
            self.player.stop()

        self.set_record(rec)
        self._playing_record = rec
        self._pending_resume_seconds = rec.play_position_seconds

        # Reset fallback panel for the new record.
        self._video_stack.setCurrentWidget(self._video_widget)
        self._video_widget.setVisible(not _is_audio_only(path))

        self.player.setSource(QUrl.fromLocalFile(path))
        self.stack.setCurrentWidget(self._player_page)
        self._player_page.setFocus()
        self.player.play()

    def stop_and_show_thumb(self) -> None:
        """Stop playback, persist final position, swap back to the thumbnail."""
        if self._playing_record is not None:
            self._persist_position()
        self._position_persist_timer.stop()
        self.player.stop()
        self.player.setSource(QUrl())  # release the file lock
        self._playing_record = None
        self._pending_resume_seconds = None
        self.stack.setCurrentWidget(self._thumb_page)

    # ── player slots ────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _seek_relative(self, delta_ms: int) -> None:
        if self._playing_record is None:
            return
        new_pos = max(0, self.player.position() + delta_ms)
        duration = self.player.duration()
        if duration > 0:
            new_pos = min(new_pos, duration)
        self.player.setPosition(new_pos)

    def _on_position_changed(self, ms: int) -> None:
        if not self._scrubber_user_dragging:
            self.scrubber.blockSignals(True)
            self.scrubber.setValue(ms)
            self.scrubber.blockSignals(False)
        duration = self.player.duration()
        self.time_label.setText(f"{_format_ms(ms)} / {_format_ms(duration)}")
        if self._playing_record is not None:
            self._position_persist_timer.start()

    def _on_duration_changed(self, ms: int) -> None:
        self.scrubber.setRange(0, max(0, ms))
        self.time_label.setText(f"{_format_ms(self.player.position())} / {_format_ms(ms)}")

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")
        # Stopped/paused → flush position so we don't lose the last 0–5s.
        if state in (
            QMediaPlayer.PlaybackState.StoppedState,
            QMediaPlayer.PlaybackState.PausedState,
        ):
            self._persist_position()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        # Resume seek must wait for LoadedMedia — duration is only valid
        # once the demuxer has read the header.
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_resume_seconds is not None:
            duration_s = self.player.duration() / 1000.0
            target = self._pending_resume_seconds
            if duration_s > 0 and _RESUME_GUARD_SECONDS < target < duration_s - _RESUME_GUARD_SECONDS:
                self.player.setPosition(int(target * 1000))
            self._pending_resume_seconds = None

    def _on_error_occurred(self, _error, _err_string: str) -> None:
        # Codec / format failure — swap to the fallback panel and stop the
        # player. We don't loop or retry; the user gets one click to open
        # the file in their OS player and walk away.
        self.player.stop()
        self._video_stack.setCurrentWidget(self._fallback_panel)

    def _on_scrubber_pressed(self) -> None:
        self._scrubber_user_dragging = True

    def _on_scrubber_released(self) -> None:
        self._scrubber_user_dragging = False
        self.player.setPosition(self.scrubber.value())

    def _on_scrubber_moved(self, value: int) -> None:
        # Live preview while dragging — apply only on release to avoid
        # constant seek thrash on every pixel of motion.
        self.time_label.setText(f"{_format_ms(value)} / {_format_ms(self.player.duration())}")

    # ── persistence ─────────────────────────────────────────────────────

    def _persist_position(self) -> None:
        """Atomically write current position to history (no-op if nothing playing)."""
        if self._playing_record is None:
            return
        pos_ms = max(0, self.player.position())
        rec = self._playing_record
        try:
            update_history_record_fields(
                HISTORY_PATH,
                rec.video_id,
                last_played_at=datetime.now(timezone.utc).isoformat(),
                play_position_seconds=pos_ms / 1000.0,
            )
        except OSError:
            # Disk write failures are non-fatal — the next tick retries.
            return
        # Reflect the persisted value back onto the in-memory record so the
        # next play() reads the current position rather than the stale one
        # that was set when the row was first loaded.
        rec.play_position_seconds = pos_ms / 1000.0

    def _open_externally(self) -> None:
        rec = self._playing_record or self._current_record
        if rec and rec.file_path:
            open_path(rec.file_path)

    # ── thumbnail cache ─────────────────────────────────────────────────

    def _lookup(self, path: str | None) -> QPixmap:
        if not path:
            return self._placeholder
        key = f"{_LARGE_CACHE_PREFIX}{path}"
        cached = QPixmapCache.find(key)
        if cached is not None:
            return cached
        pix = load_thumbnail_pixmap(path)
        if pix.isNull():
            return self._placeholder
        scaled = pix.scaled(
            PREVIEW_W,
            PREVIEW_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        QPixmapCache.insert(key, scaled)
        return scaled
