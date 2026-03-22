"""Settings panel for configuring output directory, workers, delay, and cookies."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QFileDialog,
)

from config import AppConfig, save_config


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

        # Reset button
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        layout.addRow("", self.reset_btn)

        # Auto-save on change
        self.output_dir_input.textChanged.connect(self._save)
        self.workers_spin.valueChanged.connect(self._save)
        self.delay_spin.valueChanged.connect(self._save)
        self.cookie_combo.currentTextChanged.connect(self._save)

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
        save_config(self.config)
        self.settings_changed.emit()

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        defaults = AppConfig()
        self.output_dir_input.setText(defaults.output_dir)
        self.workers_spin.setValue(defaults.workers)
        self.delay_spin.setValue(defaults.delay)
        self.cookie_combo.setCurrentIndex(0)
