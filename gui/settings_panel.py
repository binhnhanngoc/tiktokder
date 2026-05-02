"""Settings panel — Global / TikTok / Facebook sections in QGroupBoxes.

Auto-saves on every field change. `settings_changed` is emitted after each
save so MainWindow can live-propagate to the engine and browser panels.
"""

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig, save_config
from gui import theme, tokens
from health_check import HealthIssue, HealthReport

_THEME_MODE_LABELS = (("System", "system"), ("Light", "light"), ("Dark", "dark"))

# UI label → AppConfig.quality_default value (validated on save).
QUALITY_LABELS = (
    ("Best", "best"),
    ("1080p", "1080p"),
    ("720p", "720p"),
    ("480p", "480p"),
    ("Audio only", "audio"),
)


class SettingsPanel(QWidget):
    """Settings form split into three QGroupBox sections, auto-saves on change."""

    settings_changed = Signal()
    fix_action_requested = Signal(object)        # HealthIssue
    dismiss_action_requested = Signal(str)       # issue_id
    manual_refresh_requested = Signal()          # "Refresh now" pressed

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config

        outer = QVBoxLayout(self)

        outer.addWidget(self._build_health_group())
        outer.addWidget(self._build_global_group(config))
        outer.addWidget(self._build_tiktok_group(config))
        outer.addWidget(self._build_facebook_group(config))
        outer.addStretch()

        # Reset button below the groups.
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        outer.addWidget(self.reset_btn)

        # Auto-save wiring — common field set.
        self.output_dir_input.textChanged.connect(self._save)
        self.workers_spin.valueChanged.connect(self._save)
        self.delay_spin.valueChanged.connect(self._save)
        self.cookie_combo.currentTextChanged.connect(self._save)
        self.tiktok_cookies_file_input.textChanged.connect(self._save)
        self.cookies_file_input.textChanged.connect(self._save)
        self.fb_scrolls_default_spin.valueChanged.connect(self._save)
        self.quality_combo.currentIndexChanged.connect(self._save)
        self.subs_check.stateChanged.connect(self._save)

    # ── group builders ────────────────────────────────────────────────────

    def _build_global_group(self, config: AppConfig) -> QGroupBox:
        group = QGroupBox("Global")
        form = QFormLayout(group)

        # Appearance — segmented control.
        appearance_row = QHBoxLayout()
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self._theme_buttons: dict[str, QPushButton] = {}
        for label, value in _THEME_MODE_LABELS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            self._theme_buttons[value] = btn
            self.theme_group.addButton(btn)
            appearance_row.addWidget(btn)
        appearance_row.addStretch()
        active = config.theme_mode if config.theme_mode in self._theme_buttons else "system"
        self._theme_buttons[active].blockSignals(True)
        self._theme_buttons[active].setChecked(True)
        self._theme_buttons[active].blockSignals(False)
        self.theme_group.buttonToggled.connect(self._on_theme_toggled)
        form.addRow("Appearance:", appearance_row)

        # Output dir.
        dir_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(config.output_dir)
        dir_row.addWidget(self.output_dir_input, stretch=1)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(self.browse_btn)
        form.addRow("Output Directory:", dir_row)

        # Workers.
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 10)
        self.workers_spin.setValue(config.workers)
        form.addRow("Concurrent Downloads:", self.workers_spin)

        # Delay.
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(config.delay)
        form.addRow("Delay Between Downloads (s):", self.delay_spin)

        # Default quality.
        self.quality_combo = QComboBox()
        for label, value in QUALITY_LABELS:
            self.quality_combo.addItem(label, value)
        self._select_quality(config.quality_default)
        self.quality_combo.setToolTip("Audio-only and merged-stream presets require ffmpeg on PATH.")
        form.addRow("Default Quality:", self.quality_combo)

        # Subtitles toggle. Thumbnails were promoted to always-on in v1.4.0
        # (Library tab needs them for previews); the legacy
        # ``AppConfig.write_thumbnail`` field is kept untouched but no longer
        # surfaced as a UI toggle.
        self.subs_check = QCheckBox()
        self.subs_check.setChecked(config.write_subtitles)
        form.addRow("Write subtitles (en):", self.subs_check)

        return group

    def _build_tiktok_group(self, config: AppConfig) -> QGroupBox:
        group = QGroupBox("TikTok")
        form = QFormLayout(group)

        self.cookie_combo = QComboBox()
        self.cookie_combo.addItems(["None", "chrome", "firefox", "edge"])
        if config.cookie_browser:
            idx = self.cookie_combo.findText(config.cookie_browser)
            if idx >= 0:
                self.cookie_combo.setCurrentIndex(idx)
        self.cookie_combo.setToolTip("Used by yt-dlp for TikTok downloads.")
        form.addRow("Cookie Browser:", self.cookie_combo)

        # cookies.txt path — overrides Cookie Browser when set. Mirrors the
        # FB row; lifts anonymous rate limits on profile scrapes.
        tt_cookies_row = QHBoxLayout()
        self.tiktok_cookies_file_input = QLineEdit(config.tiktok_cookies_file or "")
        self.tiktok_cookies_file_input.setPlaceholderText(
            "Path to Netscape cookies.txt (optional)"
        )
        self.tiktok_cookies_file_input.setToolTip(
            "Optional. Overrides Cookie Browser. Export via 'Get cookies.txt LOCALLY' "
            "extension while logged in."
        )
        tt_cookies_row.addWidget(self.tiktok_cookies_file_input, stretch=1)
        self.tiktok_cookies_browse_btn = QPushButton("Browse...")
        self.tiktok_cookies_browse_btn.clicked.connect(self._browse_tiktok_cookies_file)
        tt_cookies_row.addWidget(self.tiktok_cookies_browse_btn)
        form.addRow("Cookies File:", tt_cookies_row)

        return group

    def _build_facebook_group(self, config: AppConfig) -> QGroupBox:
        group = QGroupBox("Facebook")
        form = QFormLayout(group)

        # cookies.txt path.
        cookies_row = QHBoxLayout()
        self.cookies_file_input = QLineEdit(config.facebook_cookies_file or "")
        self.cookies_file_input.setPlaceholderText("Path to Netscape cookies.txt (optional)")
        self.cookies_file_input.setToolTip(
            "Export Facebook cookies with a browser extension "
            "(e.g. 'Get cookies.txt LOCALLY') and point to the file here. "
            "Lifts the 10-reel cap on FB profile scraping."
        )
        cookies_row.addWidget(self.cookies_file_input, stretch=1)
        self.cookies_browse_btn = QPushButton("Browse...")
        self.cookies_browse_btn.clicked.connect(self._browse_cookies_file)
        cookies_row.addWidget(self.cookies_browse_btn)
        form.addRow("Cookies File:", cookies_row)

        # Default max scrolls — propagated to FacebookBrowserPanel on init.
        self.fb_scrolls_default_spin = QSpinBox()
        self.fb_scrolls_default_spin.setRange(1, 50)
        self.fb_scrolls_default_spin.setValue(config.facebook_max_scrolls_default)
        self.fb_scrolls_default_spin.setToolTip(
            "Default scroll iterations per fetch. Higher = more videos, slower."
        )
        form.addRow("Default Max Scrolls:", self.fb_scrolls_default_spin)

        return group

    # ── health group ──────────────────────────────────────────────────────

    def _build_health_group(self) -> QGroupBox:
        """Health section — issues list + Refresh now button. Empty when healthy."""
        group = QGroupBox("Health")
        group.setMaximumHeight(260)
        outer = QVBoxLayout(group)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.addStretch()
        self.refresh_health_btn = QPushButton("Refresh now")
        self.refresh_health_btn.setToolTip(
            "Recompute health, including the yt-dlp version check (single PyPI fetch)."
        )
        self.refresh_health_btn.clicked.connect(self.manual_refresh_requested.emit)
        header.addWidget(self.refresh_health_btn)
        outer.addLayout(header)

        # Scroll area wraps the issue list.
        self.health_list_host = QWidget()
        self.health_list_layout = QVBoxLayout(self.health_list_host)
        self.health_list_layout.setContentsMargins(0, 0, 0, 0)
        self.health_list_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.health_list_host)
        outer.addWidget(scroll, stretch=1)

        self.health_empty_label = QLabel("All good — no issues detected.")
        self.health_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.health_list_layout.addWidget(self.health_empty_label)
        self.health_list_layout.addStretch()

        return group

    def set_health_report(self, report: HealthReport) -> None:
        """Clear-and-rebuild the issues list from a fresh report."""
        # Drop existing rows (keep the empty label + stretch indices stable).
        while self.health_list_layout.count():
            item = self.health_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not report.issues:
            self.health_empty_label = QLabel("All good — no issues detected.")
            self.health_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.health_list_layout.addWidget(self.health_empty_label)
            self.health_list_layout.addStretch()
            return

        from health_check import SEVERITY_RANK

        ordered = sorted(
            report.issues,
            key=lambda i: -SEVERITY_RANK.get(i.severity, 0),
        )
        for issue in ordered:
            row = _HealthRow(issue)
            row.fix_clicked.connect(self.fix_action_requested.emit)
            row.dismiss_clicked.connect(self.dismiss_action_requested.emit)
            self.health_list_layout.addWidget(row)
        self.health_list_layout.addStretch()

    # ── helpers ───────────────────────────────────────────────────────────

    def _select_quality(self, value: str) -> None:
        for i in range(self.quality_combo.count()):
            if self.quality_combo.itemData(i) == value:
                self.quality_combo.setCurrentIndex(i)
                return
        self.quality_combo.setCurrentIndex(0)

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.config.output_dir)
        if path:
            self.output_dir_input.setText(path)

    def _browse_cookies_file(self) -> None:
        start = self.cookies_file_input.text() or self.config.output_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Facebook Cookies File",
            start,
            "Cookies (*.txt);;All files (*.*)",
        )
        if path:
            self.cookies_file_input.setText(path)

    def _browse_tiktok_cookies_file(self) -> None:
        start = self.tiktok_cookies_file_input.text() or self.config.output_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select TikTok Cookies File",
            start,
            "Cookies (*.txt);;All files (*.*)",
        )
        if path:
            self.tiktok_cookies_file_input.setText(path)

    @Slot()
    def _save(self) -> None:
        self.config.output_dir = self.output_dir_input.text()
        self.config.workers = self.workers_spin.value()
        self.config.delay = self.delay_spin.value()
        cookie = self.cookie_combo.currentText()
        self.config.cookie_browser = cookie if cookie != "None" else None
        tt_cookies_file = self.tiktok_cookies_file_input.text().strip()
        self.config.tiktok_cookies_file = tt_cookies_file or None
        fb_cookies_file = self.cookies_file_input.text().strip()
        self.config.facebook_cookies_file = fb_cookies_file or None
        self.config.facebook_max_scrolls_default = self.fb_scrolls_default_spin.value()
        self.config.quality_default = self.quality_combo.currentData() or "best"
        self.config.write_subtitles = self.subs_check.isChecked()
        save_config(self.config)
        self.settings_changed.emit()

    def _reset_defaults(self) -> None:
        defaults = AppConfig()
        self.output_dir_input.setText(defaults.output_dir)
        self.workers_spin.setValue(defaults.workers)
        self.delay_spin.setValue(defaults.delay)
        self.cookie_combo.setCurrentIndex(0)
        self.tiktok_cookies_file_input.clear()
        self.cookies_file_input.clear()
        self.fb_scrolls_default_spin.setValue(defaults.facebook_max_scrolls_default)
        self._select_quality(defaults.quality_default)
        self.subs_check.setChecked(defaults.write_subtitles)
        sys_btn = self._theme_buttons["system"]
        sys_btn.blockSignals(True)
        sys_btn.setChecked(True)
        sys_btn.blockSignals(False)
        theme.set_mode("system")
        self.config.theme_mode = "system"
        save_config(self.config)

    @Slot(object, bool)
    def _on_theme_toggled(self, button, checked: bool) -> None:
        if not checked:
            return
        for value, btn in self._theme_buttons.items():
            if btn is button:
                theme.set_mode(value)
                self.config.theme_mode = value
                save_config(self.config)
                self.settings_changed.emit()
                return


# Action-kind → button copy. Empty label = no action button rendered.
_ACTION_LABELS = {
    "open_path": "Open file",
    "open_url": "Open releases",
    "refresh_channel": "Refresh now",
    "none": "",
}


class _HealthRow(QWidget):
    """One issue row: severity dot · title · detail · action btn · dismiss btn."""

    fix_clicked = Signal(object)       # HealthIssue
    dismiss_clicked = Signal(str)      # issue_id

    def __init__(self, issue: HealthIssue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._issue = issue
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(
            f"QLabel {{ background: {_severity_color(issue.severity)}; "
            f"border-radius: 6px; }}"
        )
        layout.addWidget(dot)

        title = QLabel(issue.title)
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        if issue.detail:
            detail = QLabel(issue.detail)
            detail.setStyleSheet(f"color: {tokens.token('text.muted')};")
            detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            detail.setToolTip(issue.detail)
            layout.addWidget(detail, stretch=1)
        else:
            layout.addStretch()

        action_label = _ACTION_LABELS.get(issue.fix_action_kind, "")
        if action_label:
            self.fix_btn = QPushButton(action_label)
            self.fix_btn.clicked.connect(
                lambda _checked=False: self.fix_clicked.emit(self._issue)
            )
            layout.addWidget(self.fix_btn)

        self.dismiss_btn = QPushButton("×")
        self.dismiss_btn.setFixedWidth(24)
        self.dismiss_btn.setToolTip("Dismiss this issue.")
        self.dismiss_btn.clicked.connect(
            lambda _checked=False: self.dismiss_clicked.emit(self._issue.id)
        )
        layout.addWidget(self.dismiss_btn)


def _severity_color(severity: str) -> str:
    """Map severity to a theme-aware token color (mirrors StatusBarWidget)."""
    if severity == "error":
        return tokens.token("state.error")
    if severity == "info":
        return tokens.token("state.info")
    return tokens.token("state.warning")
