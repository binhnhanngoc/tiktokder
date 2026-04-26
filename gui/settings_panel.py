"""Settings panel for configuring output directory, workers, delay, and cookies."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from config import AppConfig, save_config

# UI label → AppConfig.quality_default value (validated on save).
QUALITY_LABELS = (
    ("Best", "best"),
    ("1080p", "1080p"),
    ("720p", "720p"),
    ("480p", "480p"),
    ("Audio only", "audio"),
)


class SettingsPanel(QWidget):
    """Settings form that auto-saves on change."""

    # Emitted when settings change so engine can update live
    settings_changed = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config

        layout = QFormLayout(self)

        # Output directory
        dir_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(config.output_dir)
        dir_row.addWidget(self.output_dir_input, stretch=1)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(self.browse_btn)
        layout.addRow("Output Directory:", dir_row)

        # Workers
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 10)
        self.workers_spin.setValue(config.workers)
        layout.addRow("Concurrent Downloads:", self.workers_spin)

        # Delay
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(config.delay)
        layout.addRow("Delay Between Downloads (s):", self.delay_spin)

        # Cookie browser
        self.cookie_combo = QComboBox()
        self.cookie_combo.addItems(["None", "chrome", "firefox", "edge"])
        if config.cookie_browser:
            idx = self.cookie_combo.findText(config.cookie_browser)
            if idx >= 0:
                self.cookie_combo.setCurrentIndex(idx)
        layout.addRow("Cookie Browser:", self.cookie_combo)

        # Default quality
        self.quality_combo = QComboBox()
        for label, value in QUALITY_LABELS:
            self.quality_combo.addItem(label, value)
        self._select_quality(config.quality_default)
        self.quality_combo.setToolTip("Audio-only and merged-stream presets require ffmpeg on PATH.")
        layout.addRow("Default Quality:", self.quality_combo)

        # Subtitles
        self.subs_check = QCheckBox()
        self.subs_check.setChecked(config.write_subtitles)
        layout.addRow("Write subtitles (en):", self.subs_check)

        # Thumbnails
        self.thumb_check = QCheckBox()
        self.thumb_check.setChecked(config.write_thumbnail)
        layout.addRow("Write thumbnail:", self.thumb_check)

        # Reset button
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        layout.addRow("", self.reset_btn)

        # Auto-save on change
        self.output_dir_input.textChanged.connect(self._save)
        self.workers_spin.valueChanged.connect(self._save)
        self.delay_spin.valueChanged.connect(self._save)
        self.cookie_combo.currentTextChanged.connect(self._save)
        self.quality_combo.currentIndexChanged.connect(self._save)
        self.subs_check.stateChanged.connect(self._save)
        self.thumb_check.stateChanged.connect(self._save)

    def _select_quality(self, value: str) -> None:
        """Move combo selection to the entry whose userData matches ``value``."""
        for i in range(self.quality_combo.count()):
            if self.quality_combo.itemData(i) == value:
                self.quality_combo.setCurrentIndex(i)
                return
        self.quality_combo.setCurrentIndex(0)  # default to "Best"

    def _browse_output_dir(self) -> None:
        """Open native directory picker."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.config.output_dir)
        if path:
            self.output_dir_input.setText(path)

    @Slot()
    def _save(self) -> None:
        """Persist current settings to config file."""
        self.config.output_dir = self.output_dir_input.text()
        self.config.workers = self.workers_spin.value()
        self.config.delay = self.delay_spin.value()
        cookie = self.cookie_combo.currentText()
        self.config.cookie_browser = cookie if cookie != "None" else None
        self.config.quality_default = self.quality_combo.currentData() or "best"
        self.config.write_subtitles = self.subs_check.isChecked()
        self.config.write_thumbnail = self.thumb_check.isChecked()
        save_config(self.config)
        self.settings_changed.emit()

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        defaults = AppConfig()
        self.output_dir_input.setText(defaults.output_dir)
        self.workers_spin.setValue(defaults.workers)
        self.delay_spin.setValue(defaults.delay)
        self.cookie_combo.setCurrentIndex(0)
        self._select_quality(defaults.quality_default)
        self.subs_check.setChecked(defaults.write_subtitles)
        self.thumb_check.setChecked(defaults.write_thumbnail)
