# An MCP server and Claude Code plugin for PyMOL+

**Goal:** Claude can work with PyMOL+ in three ways through one MCP server: drive the PyMOL+ that is open on screen, analyse structures in a headless PyMOL, and help write PyMOL scripts and plugins through a Claude Code plugin with PyMOL skills.

**Architecture:** `pymol3.mcp` is a stdio MCP server that Claude starts. It looks for a running PyMOL+ whose live mode is on and talks to it over a local, token-protected socket (`pymol3.bridge`, a plain-Python socket server running inside the app on a worker thread under PyMOL's API lock); without one, it starts its own windowless PyMOL running the same bridge. Both offer the same tools. A Claude Code plugin registers the server and ships skills.

**Tech Stack:** Python, the MCP Python SDK (`mcp`), Python sockets and threads (no Qt in the bridge, so headless works from a pip install without Qt), PyMOL `cmd`, Claude Code plugin format (`.claude-plugin/plugin.json`, `.mcp.json`, skills), Bazel (`rules_python`), pytest.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: the Notion list's "MCP server/ Claude Code plugin".

## Design

**Why.** Scientists should be able to ask Claude to work in PyMOL+ for them: while they look at a structure ("colour the binding pocket and make a figure for my talk"), in the background on many files (distances, contacts, alignments), and when writing PyMOL scripts and plugins. All three must be possible.

**What the user sees.**

- **Live mode.** **Plugin → Allow Claude to control PyMOL+** switches it on (off by default, remembered); the status bar shows "Claude connected" while a client is attached, with a button to disconnect. Commands Claude runs appear in the output panel and the command history like typed ones. The Plugin menu entries are added after `initializePlugins()`, which clears `menudict['Plugin']` (`pymol_qt_gui.py`), to `menudict['PluginQt']`.
- **Headless mode.** When no PyMOL+ with live mode is open, or when Claude is asked for it (`mode="headless"`), the server starts its own windowless PyMOL that stays alive (`pymol -cqK` with the bridge started as a thread from a `-d`/startup script, since a bare `pymol -cq` exits when its input ends) and stops it when the session ends.
- **Tools** (the same in both modes):
  - `run_pymol` – run any PyMOL command-language lines, Python and shell included (developer's choice), returning output and errors;
  - `run_python` – run Python in PyMOL's interpreter with `cmd` available, returning output and the value of the last expression;
  - `load` / `fetch`, `list_objects` (objects, selections, groups, states), `get_view` / `set_view`;
  - `measure` (distance, angle, dihedral, contacts within a cutoff), `align` (RMSD);
  - `render_image` – ray-trace or draw the current view at a given size and return it as an image, so Claude sees what it did;
  - `save` – session, structure or image to a path.
- **Claude Code plugin** "pymol-plus": registers the server (`pymol-mcp`), and brings skills: PyMOL's command reference, writing PyMOL scripts and plugins (including `pymol3`), and recipes for figures and common analyses. Installed with `claude plugin marketplace add Convergent-Binding/pymol-plus` and `claude plugin install pymol-plus`.
- The Claude app (desktop) can use the same server through its MCP configuration.

**Approaches considered.**

- **A. One stdio MCP server that attaches to the open app or starts a headless PyMOL (chosen).** One setup covers all three uses; the plugin registers one server.
- B. The app itself as an HTTP MCP server. No extra process, but only while the app runs, so headless mode needs a second server and a second configuration. Rejected.
- C. PyMOL's old XML-RPC server (`pymol -R`, `rpc.py`). Exists, but has no authentication: any program on the machine could control PyMOL. Rejected.

**Decisions made with the developer.**

- All three uses: live, headless, scripting help.
- Claude may run any PyMOL command, Python and shell included (option B of the safety question), for maximum flexibility.
- Built as approach A.
- The app gets **Plugin → Install `pymol-mcp` command**, like VS Code's "Install 'code' command in PATH": it installs a small console launcher `pymol-mcp` into a folder on the user's `PATH` (Windows: a console-subsystem launcher in the user's local programs folder added to the user `PATH`; macOS and Linux: a link in `~/.local/bin`). Pip users get the same command from the wheel's `mcp` extra. The plugin's `.mcp.json` runs `pymol-mcp` everywhere (reviewer question, accepted 2026-11-23).
- Each new connection asks once in PyMOL+: "Claude wants to control PyMOL+: Allow / Deny"; the answer holds until the app closes. Without an answer within 60 seconds the connection is refused with a clear message, so a scheduled session does not hang. Commands stay unrestricted (reviewer question, accepted 2026-11-23).

**Calls made in the design (Claude's, open to correction).**

- **Shared GUI hooks** (all PyMOL+ GUI features: `command-palette.md`, `scenes-panel.md`, `objects-panel.md`, `project-library.md`, `mcp-server.md`): the app's edited `pymol_qt_gui.py` gets exactly two marked segments, one at start-up that calls `pymol3.app.start(window)` and one in `update_feedback()` that hands every tick and every feedback batch to `pymol3.app.tick(window, feedback)`. Features register with `pymol3.app` instead of adding segments of their own; whichever feature lands first adds both segments and `pymol3.app`, and also `pymol3.ui.add_dock_panel(..., visible=True)` if it is not there yet.
- Safeguards that cost no flexibility: live mode is off by default and switched on in the app's menu; each new connection is confirmed in the app (see Decisions); the bridge listens only on the local machine (a local socket, or `localhost` TCP), with a random token written to a file only the user can read; Claude Code's own permission prompt asks before tool calls unless the user allows them.
- The bridge runs each request on its own worker thread under PyMOL's API lock (as PyMOL's own threads and plugins do), so the GUI stays responsive: the user can keep working, Disconnect works, and a second client is told "already connected".
- Timeouts (default 120 s, per tool call adjustable): the bridge first calls `cmd.interrupt()` (stops ray tracing and other C work), then raises an exception in the request's thread (`PyThreadState_SetAsyncExc`, which ends Python loops and sleeps), and reports the timeout. A shell command it started cannot be ended that way and is reported as still running; in headless mode the server can end the whole child process.
- Output capture: PyMOL's feedback through the feedback fan-out in the app (see Facts), Python output by swapping `sys.stdout`/`sys.stderr` for the request's thread, and in headless mode C output by redirecting file descriptor 1 for the request's duration, since `pymol -cq` queues no feedback.
- Sessions: the mode is chosen on the first tool call (live if a live PyMOL+ is found, else headless, or as asked) and kept for the session; every result names which PyMOL answered. A `connect` tool switches explicitly (`mode`, `instance`). If the live PyMOL+ closes or live mode is switched off mid-session, tools report an error instead of silently starting a fresh headless PyMOL.
- Several PyMOL+ windows with live mode on: each writes its own discovery file (process id, socket, token) in the user's runtime folder; the server attaches to the most recently started one, and `list_instances` plus `connect(instance=…)` choose another.
- `render_image` returns PNG at most 1600 px on the long side by default, to keep it light for the model.
- `pymol3.mcp` and its dependencies are an optional extra of the wheel (`pip install "pymol-open-source-whl[mcp]"`) and are included in the app; the wheel's console script and the app's console launcher are both called `pymol-mcp`.
- The plugin lives under `integrations/claude-code/`; the marketplace file is `.claude-plugin/marketplace.json` at the repository root, pointing at it, which is where `claude plugin marketplace add Convergent-Binding/pymol-plus` looks.
- One client at a time in live mode; a second gets a clear "already connected" error.

**Facts from the code that bind the design.**

- `modules/pymol/rpc.py` (XML-RPC, `pymol -R`) and `modules/pymol/pymolhttpd.py` exist and are unauthenticated; this feature does not use or change them.
- In the Qt GUI, typed commands run through `doTypedCommand()` and feedback is read only by `update_feedback()` from `cmd._get_feedback()` (`distribution/edited/pmg_qt/pymol_qt_gui.py`), which hands each line out once. The command palette feature plans a fan-out hook there (`features/command-palette.md`, step 2) that is not built yet: whichever of the two features lands first adds that hook in the marked segment, and the other uses it.
- In `pymol -cq`, `pmgui` is 0, so `OrthoFeedbackIn` (`layer1/Ortho.cpp`) queues nothing; output goes to C `printf` on file descriptor 1. `pcatch` is installed only by the Qt GL widget.
- The wheel depends on numpy only, so a pip-only setup has no Qt; the bridge therefore uses plain Python sockets.
- `cmd.interrupt()` (`modules/pymol/locking.py`) only sets PyMOL's C interrupt flag.
- "The output panel" is the command palette feature's bottom panel when it exists, otherwise the External GUI's output view.

## Global Constraints

Quoted from AGENTS.md:

- No file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes; new code lives in `pymol3`, the app hook in `distribution/edited/`.
- "New dependency versions only when they are at least 14 days old."
- "App package and AppStream license: `BSD-3-Clause AND LGPL-3.0-only AND HPND`"; the MCP SDK and its dependencies join the bundle's third-party licence files.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only."
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/requirements.in
distribution/requirements_lock.txt
distribution/licenses/**
tools/bazel/**
pyproject.toml
integrations/claude-code/**
.claude-plugin/**
distribution/docs/website/**
distribution/launcher/**
distribution/bundle/**
distribution/windows/**
distribution/macos/**
distribution/linux/**

## Done

All three steps below are merged into `production`; Claude Code with the plugin drives an open PyMOL+, runs a headless analysis, and uses the skills to write a working PyMOL script.

## Non-goals

- Changing or securing PyMOL's old XML-RPC and HTTP servers.
- Remote access from other machines; live mode is local only.
- Several Claude clients controlling one PyMOL+ at once.
- Restricting which commands Claude may run (decided: everything is allowed).
- A Claude chat inside PyMOL+.

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts.

1. **The bridge and live mode** (`mcp-bridge`): `pymol3.bridge` (protocol, token, discovery files, local socket, worker-thread execution under the API lock, timeouts, capturing output through the shared `pymol3.app.tick` feedback fan-out, errors and images), registration through the shared GUI hooks (adding them if this lands first), the menu toggle, the per-connection question, the status indicator and disconnect, and the same bridge in a headless PyMOL kept alive with `-K`.
2. **The MCP server** (`mcp-server`): `pymol3.mcp` with the tools, `connect` and `list_instances`, discovery of a live PyMOL+ and the headless fallback, the `mcp` extra in the wheel with its `pymol-mcp` console script, the app's bundle and its licence files, the app's console launcher `pymol-mcp` and the menu entry that installs it on the `PATH`.
3. **The Claude Code plugin and docs** (`mcp-plugin`): the plugin under `integrations/claude-code/` (manifest, `.mcp.json`, skills), `.claude-plugin/marketplace.json` at the repository root, and a website page on using PyMOL+ with Claude.

## Review Focus

- **Other local programs taking control.** A web page or another user on the machine must not reach the bridge. Covered by tests that connect without the token, with a wrong token, and (on shared machines) as another user, and by binding only to the local machine.
- **A request that never returns.** A long ray trace, an endless Python loop or a `sleep` must not hang Claude or the GUI. Covered by tests for each with a short timeout: interrupt, async exception, report, GUI still responsive.
- **Output of one request leaking into another.** Feedback from the user's own typing must not appear in Claude's results. Covered by a test that types a command while a request runs.
- **The headless PyMOL left running.** Covered by a test that ends the MCP session and checks the child process is gone.

## Acceptance criteria

- With live mode on, Claude Code (with the plugin) loads a structure, colours a selection and renders an image of the open PyMOL+, and the user sees each command in the output panel.
- Without a live PyMOL+, the same tools run in a headless PyMOL; it stops when the session ends.
- `run_pymol` and `run_python` run anything, Python and shell included, and return output and errors.
- The bridge refuses connections without the right token; live mode is off until switched on, each new connection is confirmed in the app (refused after 60 seconds without an answer), and the app shows when Claude is connected.
- Plugin → Install `pymol-mcp` command makes `pymol-mcp` runnable from a new terminal on Windows, macOS and Linux; `pip install "pymol-open-source-whl[mcp]"` gives the same command.
- The plugin installs from this repository's marketplace and its skills are available in Claude Code.
- No upstream file changes (the app hooks are in `distribution/edited/`); `bazel test //...` and `bazel test //distribution/...` pass.

## Verification

- `bazel test //tests/...` runs the bridge tests (token, local-only binding, worker-thread execution under the API lock with the GUI responsive during a request, output capture, timeout) against a headless PyMOL, and the MCP server tests through an MCP client over stdio in both modes.
- `bazel test //distribution/...` passes, the app's smoke test included.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand: Claude Code with the plugin against the app on Windows and macOS, live and headless.
