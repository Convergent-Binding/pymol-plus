# SPDX-License-Identifier: BSD-3-Clause
"""A feature module as the PyMOL+ GUI features write one, for the tests.

Importing it registers one feature, ``sample``, whose start and ready note
their calls in ``CALLS``.
"""

from pymol3 import app

CALLS = []
"""Receives ``"start"`` and ``"ready"`` as the feature runs."""

app.register(
    app.Feature(
        name="sample",
        start=lambda window: CALLS.append("start"),
        ready=lambda window: CALLS.append("ready"),
    )
)
