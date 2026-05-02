"""Widget smoke tests — pill color flips + Settings group rebuilds + dismiss signal."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGroupBox

from config import AppConfig
from health_check import HealthIssue, HealthReport


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _report(*issues: HealthIssue) -> HealthReport:
    return HealthReport(issues=list(issues), computed_at="2026-05-02T00:00:00+00:00")


def _issue(severity: str, *, id_: str = "x", **kwargs) -> HealthIssue:
    return HealthIssue(id=id_, severity=severity, title="t", **kwargs)


# ── status pill ───────────────────────────────────────────────────────────


def test_status_pill_severity_property_flips(qapp) -> None:
    """``set_health_report`` writes the severity property used by QSS."""
    from gui.status_bar_widget import StatusBarWidget

    widget = StatusBarWidget()
    widget.set_health_report(_report(_issue("warn")))
    assert widget.health_pill.property("severity") == "warn"

    widget.set_health_report(_report(_issue("error", id_="e")))
    assert widget.health_pill.property("severity") == "error"

    widget.set_health_report(_report())  # empty
    assert widget.health_pill.property("severity") == "ok"


def test_status_pill_caches_issues_for_popover(qapp) -> None:
    """Issues stored on the widget so the popover can render them."""
    from gui.status_bar_widget import StatusBarWidget

    widget = StatusBarWidget()
    widget.set_health_report(_report(_issue("info"), _issue("error", id_="e")))
    assert len(widget._issues) == 2


# ── settings panel ────────────────────────────────────────────────────────


def test_settings_panel_includes_health_group(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    titles = sorted(g.title() for g in panel.findChildren(QGroupBox))
    assert "Health" in titles


def test_settings_health_group_rebuilds_on_report(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel, _HealthRow

    panel = SettingsPanel(AppConfig())
    panel.set_health_report(_report(
        _issue("error", id_="a"),
        _issue("warn", id_="b"),
        _issue("info", id_="c"),
    ))
    rows = [
        panel.health_list_layout.itemAt(i).widget()
        for i in range(panel.health_list_layout.count())
        if panel.health_list_layout.itemAt(i).widget() is not None
    ]
    assert len(rows) == 3
    assert all(isinstance(r, _HealthRow) for r in rows)


def test_settings_health_empty_state(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    panel.set_health_report(_report())
    # One QLabel ("All good — …") + a stretch.
    widgets = [
        panel.health_list_layout.itemAt(i).widget()
        for i in range(panel.health_list_layout.count())
    ]
    labels = [w for w in widgets if w is not None and w.metaObject().className() == "QLabel"]
    assert any("All good" in lbl.text() for lbl in labels)


def test_settings_dismiss_button_emits_id(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    captured: list[str] = []
    panel.dismiss_action_requested.connect(captured.append)
    panel.set_health_report(_report(_issue("warn", id_="dismiss-me")))
    # Find the row and click its dismiss button.
    row = panel.health_list_layout.itemAt(0).widget()
    row.dismiss_btn.click()
    assert captured == ["dismiss-me"]


def test_settings_fix_button_emits_issue(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    captured: list[HealthIssue] = []
    panel.fix_action_requested.connect(captured.append)
    issue = _issue(
        "warn",
        id_="fix-me",
        fix_action_kind="refresh_channel",
        fix_action_arg="https://x",
    )
    panel.set_health_report(_report(issue))
    row = panel.health_list_layout.itemAt(0).widget()
    row.fix_btn.click()
    assert captured == [issue]


def test_settings_manual_refresh_signal(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    captured: list[bool] = []
    panel.manual_refresh_requested.connect(lambda: captured.append(True))
    panel.refresh_health_btn.click()
    assert captured == [True]
