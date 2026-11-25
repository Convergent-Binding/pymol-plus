# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.app: the GUI style, the features and the menu entry."""

import pytest

from pymol3 import app

from ..pymol3_ui import qt_binding

# Skips this module without a Qt binding, unless the setup requires one.
qt = qt_binding.import_qt()
"""The Qt binding PyMOL found."""


class _Recorder:
  """A feature's callbacks that note each call in a shared list."""

  def __init__(self, calls: list) -> None:
    """Keeps the list the calls go to.

    Args:
      calls: Receives ``(feature name, phase)`` for every call.
    """
    self.calls = calls
    """Receives ``(feature name, phase)`` for every call."""

  def feature(self, name: str) -> app.Feature:
    """Makes a feature whose start and ready only note their call.

    Args:
      name: The feature's name.

    Returns:
      The feature.
    """
    return app.Feature(
        name=name,
        start=lambda window: self.calls.append((name, "start")),
        ready=lambda window: self.calls.append((name, "ready")),
    )


def _new_gui_action(window):
  """Finds the New GUI entry of the window's Display menu.

  Args:
    window: The main window.

  Returns:
    The action, or None when the menu has none.
  """
  for tmp_action in window.menudict["Display"].actions():
    if tmp_action.text() == "New GUI":
      return tmp_action
  return None


def test_style_defaults_to_classic():
  """With no option and no stored choice, the classic GUI runs."""
  assert app.style() == app.CLASSIC
  assert app.DEFAULT_STYLE == app.CLASSIC


def test_style_from_stored_choice():
  """A stored choice decides the style when nothing overrides it."""
  app.store_style(app.NEW)
  assert app.stored_style() == app.NEW
  assert app.style() == app.NEW


def test_style_environment_wins_over_stored(monkeypatch):
  """The environment variable, set by the command line, wins.

  Args:
    monkeypatch: Sets the environment variable.
  """
  app.store_style(app.NEW)
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, "classic")
  assert app.style() == app.CLASSIC


def test_style_environment_ignores_case(monkeypatch):
  """The environment variable is read without regard to case or spaces.

  Args:
    monkeypatch: Sets the environment variable.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, " New ")
  assert app.style() == app.NEW


def test_style_ignores_invalid_values(monkeypatch, capsys):
  """Unknown values fall back to the next source and are reported.

  Args:
    monkeypatch: Sets the environment variable.
    capsys: Captures PyMOL's output.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, "fancy")
  app._open_settings().setValue(app.SETTINGS_KEY, "shiny")
  assert app.style() == app.CLASSIC
  tmp_output = capsys.readouterr().out
  assert "'fancy'" in tmp_output
  assert "'shiny'" in tmp_output


def test_style_fixed_for_the_run():
  """A choice stored during the run applies from the next start only."""
  assert app.style() == app.CLASSIC
  app.store_style(app.NEW)
  assert app.style() == app.CLASSIC


def test_store_style_rejects_unknown():
  """Only the two style names can be stored."""
  with pytest.raises(ValueError):
    app.store_style("fancy")


def test_register_twice_raises():
  """A feature name registers once."""
  app.register(app.Feature(name="objects"))
  with pytest.raises(ValueError):
    app.register(app.Feature(name="objects"))


def test_classic_style_runs_no_feature(main_window):
  """In the classic style neither start nor ready of a feature runs.

  Args:
    main_window: The main window.
  """
  tmp_calls = []
  app.register(_Recorder(tmp_calls).feature("objects"))
  app.start(main_window)
  app.ready(main_window)
  assert tmp_calls == []


def test_new_style_runs_start_and_ready(monkeypatch, main_window):
  """In the new style every feature's start runs, then every ready.

  Args:
    monkeypatch: Sets the environment variable.
    main_window: The main window.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.NEW)
  tmp_calls = []
  tmp_recorder = _Recorder(tmp_calls)
  app.register(tmp_recorder.feature("objects"))
  app.register(tmp_recorder.feature("palette"))
  app.start(main_window)
  app.ready(main_window)
  assert tmp_calls == [
      ("objects", "start"),
      ("palette", "start"),
      ("objects", "ready"),
      ("palette", "ready"),
  ]


def test_feature_without_callbacks(monkeypatch, main_window):
  """A feature may leave out start, ready or both.

  Args:
    monkeypatch: Sets the environment variable.
    main_window: The main window.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.NEW)
  app.register(app.Feature(name="objects"))
  app.start(main_window)
  app.ready(main_window)


def test_failing_feature_does_not_stop_others(
    monkeypatch, main_window, capsys
):
  """A feature that raises is reported and skipped; the others run.

  Args:
    monkeypatch: Sets the environment variable.
    main_window: The main window.
    capsys: Captures PyMOL's output.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.NEW)
  tmp_calls = []

  def tmp_fail(window):
    """Fails as a broken feature would.

    Args:
      window: The main window.

    Raises:
      RuntimeError: Always.
    """
    raise RuntimeError("broken feature")

  app.register(
      app.Feature(
          name="broken",
          start=tmp_fail,
          ready=lambda window: tmp_calls.append(("broken", "ready")),
      )
  )
  app.register(_Recorder(tmp_calls).feature("objects"))
  app.start(main_window)
  app.ready(main_window)
  assert tmp_calls == [("objects", "start"), ("objects", "ready")]
  assert "broken feature" in capsys.readouterr().err


def test_menu_hidden_without_features(monkeypatch, main_window):
  """With no feature registered, the Display menu has no New GUI entry.

  Args:
    monkeypatch: Sets the environment variable.
    main_window: The main window.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.NEW)
  app.start(main_window)
  app.ready(main_window)
  assert _new_gui_action(main_window) is None


@pytest.mark.parametrize(
    ("style", "checked"), [(app.NEW, True), (app.CLASSIC, False)]
)
def test_menu_entry_shows_style(monkeypatch, main_window, style, checked):
  """The New GUI entry is checked exactly in the new style.

  Args:
    monkeypatch: Sets the environment variable.
    main_window: The main window.
    style: The style of the run.
    checked: Whether the entry must be checked.
  """
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, style)
  app.register(app.Feature(name="objects"))
  app.start(main_window)
  app.ready(main_window)
  tmp_action = _new_gui_action(main_window)
  assert tmp_action is not None
  assert tmp_action.isCheckable()
  assert tmp_action.isChecked() is checked


def test_menu_entry_once(main_window):
  """A second ready adds no second entry.

  Args:
    main_window: The main window.
  """
  app.register(app.Feature(name="objects"))
  app.ready(main_window)
  app.ready(main_window)
  tmp_texts = [
      tmp_action.text()
      for tmp_action in main_window.menudict["Display"].actions()
  ]
  assert tmp_texts.count("New GUI") == 1


def test_menu_entry_stores_choice_for_next_start(main_window):
  """Toggling the entry stores the choice and says a restart applies it.

  Args:
    main_window: The main window.
  """
  app.register(app.Feature(name="objects"))
  app.start(main_window)
  app.ready(main_window)
  _new_gui_action(main_window).trigger()
  assert app.stored_style() == app.NEW
  assert app.style() == app.CLASSIC
  tmp_boxes = main_window.findChildren(qt.QtWidgets.QMessageBox)
  assert len(tmp_boxes) == 1
  assert "restart" in tmp_boxes[0].text()
  tmp_boxes[0].close()
  _new_gui_action(main_window).trigger()
  assert app.stored_style() == app.CLASSIC


def test_menu_needs_no_display_menu(bare_main_window):
  """A window without PyMOL's menus gets no entry and no error.

  Args:
    bare_main_window: A main window without ``menudict``.
  """
  app.register(app.Feature(name="objects"))
  app.start(bare_main_window)
  app.ready(bare_main_window)
