"""Tests for gui/update_dialog.UpdateAvailableDialog."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.update_dialog import UpdateAvailableDialog
from update_checker import ReleaseInfo


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _release(version=(1, 10, 1), body="# Notes\n- improvement", fallback=False):
    vs = f"{version[0]}.{version[1]}.{version[2]}"
    return ReleaseInfo(
        version=version,
        version_str=vs,
        html_url=f"https://github.com/x/y/releases/tag/v{vs}",
        body=body,
        is_tag_fallback=fallback,
    )


class TestRendering:
    def test_header_contains_versions(self, qapp):
        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        # Header text is a QLabel with rich text — search the dialog's
        # children for one containing both versions.
        from PySide6.QtWidgets import QLabel

        labels = dlg.findChildren(QLabel)
        any_match = any(
            "1.10.1" in lbl.text() and "1.9.0" in lbl.text()
            for lbl in labels
        )
        assert any_match, [lbl.text() for lbl in labels]

    def test_window_title(self, qapp):
        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        assert "Update available" in dlg.windowTitle()

    def test_modal(self, qapp):
        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        assert dlg.isModal() is True

    def test_tag_fallback_shows_placeholder(self, qapp):
        from PySide6.QtWidgets import QTextBrowser

        dlg = UpdateAvailableDialog(_release(body="", fallback=True), "1.9.0", False)
        bodies = dlg.findChildren(QTextBrowser)
        assert bodies, "expected one QTextBrowser body widget"
        text = bodies[0].toPlainText()
        assert "No release notes" in text


class TestCheckbox:
    def test_initial_unchecked_when_opt_out_false(self, qapp):
        from PySide6.QtWidgets import QCheckBox

        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        cb = dlg.findChild(QCheckBox)
        assert cb is not None
        assert cb.isChecked() is False
        assert dlg.opt_out_chosen() is False

    def test_initial_checked_when_opt_out_true(self, qapp):
        from PySide6.QtWidgets import QCheckBox

        dlg = UpdateAvailableDialog(_release(), "1.9.0", True)
        cb = dlg.findChild(QCheckBox)
        assert cb is not None
        assert cb.isChecked() is True
        assert dlg.opt_out_chosen() is True

    def test_opt_out_chosen_reflects_toggle(self, qapp):
        from PySide6.QtWidgets import QCheckBox

        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        cb = dlg.findChild(QCheckBox)
        cb.setChecked(True)
        assert dlg.opt_out_chosen() is True
        cb.setChecked(False)
        assert dlg.opt_out_chosen() is False


class TestSkipSignal:
    def test_skip_button_emits_with_version(self, qapp):
        from PySide6.QtWidgets import QPushButton

        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        captured: list[str] = []
        dlg.skip_requested.connect(captured.append)
        skip_btn = next(
            b for b in dlg.findChildren(QPushButton) if "Skip" in b.text()
        )
        skip_btn.click()
        assert captured == ["1.10.1"]

    def test_remind_later_does_not_emit_skip(self, qapp):
        from PySide6.QtWidgets import QPushButton

        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        captured: list[str] = []
        dlg.skip_requested.connect(captured.append)
        later_btn = next(
            b for b in dlg.findChildren(QPushButton) if "Remind" in b.text()
        )
        later_btn.click()
        assert captured == []


class TestButtons:
    def test_three_buttons_present(self, qapp):
        from PySide6.QtWidgets import QPushButton

        dlg = UpdateAvailableDialog(_release(), "1.9.0", False)
        labels = [b.text() for b in dlg.findChildren(QPushButton)]
        for needle in ("Open Release Page", "Skip This Version", "Remind Me Later"):
            assert needle in labels, f"missing button {needle!r} (have {labels})"
