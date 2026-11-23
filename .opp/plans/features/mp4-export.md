# MP4 export for talks, with a bundled LGPL ffmpeg

**Goal:** File → Export Movie As… writes an H.264 `.mp4` that plays in PowerPoint and Keynote on every PyMOL+ platform out of the box, using the operating system's own H.264 encoder on Windows and macOS and Cisco's OpenH264 (downloaded from Cisco after asking) on Linux, without GPL code and without changing the app's licence.

**Architecture:** The app bundle gains an LGPL build of ffmpeg without x264 for each platform, put on the `PATH` at start-up, where PyMOL's existing `movie.produce` already looks for it. A marked edit in an app copy of `modules/pymol/movie.py` under `distribution/edited/` chooses the H.264 encoder explicitly per platform (Media Foundation, VideoToolbox or OpenH264) with matching quality options, and on Linux fetches OpenH264 from Cisco on first use after the user agrees.

**Tech Stack:** FFmpeg (LGPL build: `h264_mf`, `h264_videotoolbox`, `libopenh264`, `libvpx` for WebM), Cisco OpenH264 binaries, Python, Bazel (`http_archive` with checksums, `rules_pkg`), the app's `startup_wrapper.py`.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: the Notion list's "Direct MP4 export by including ffmpeg".

## Design

**Why.** Scientists export PyMOL movies mainly for talks, in PowerPoint and Keynote. Today export fails unless the user has installed ffmpeg on their own, and a typical ffmpeg build uses x264 (GPL), which PyMOL+ cannot ship under its licence. Those programs reliably play only H.264 in `.mp4`.

**What the user sees.**

- File → Export Movie As… → MPEG-4 (`.mp4`) and QuickTime (`.mov`) work on a fresh install, with no ffmpeg of their own, and both carry H.264.
- **Windows and macOS:** encoding uses the operating system's H.264 encoder (Media Foundation, VideoToolbox); no download, no question.
- **Linux, and Windows N editions without Media Foundation's H.264 encoder:** the first MP4 export asks once, in the Export Movie dialog: "MP4 export needs Cisco's OpenH264 encoder. Download it from Cisco (about 1 MB)? Cisco provides it free of charge and pays the H.264 patent licence." With **Download**, PyMOL+ fetches it from Cisco, checks it, keeps it in the user's cache and exports. With **Not now**, the export offers WebM or animated GIF instead. The dialog's encoder options keep a checkbox **Use Cisco's OpenH264 (downloaded)** to change that choice later, and the About box and the licence files carry Cisco's credit "OpenH264 Video Codec provided by Cisco Systems, Inc."
- A script or `pymol -c` export of MP4 without an H.264 encoder stops with a message that names the missing encoder and how to enable OpenH264 (`pymol3.movie.enable_openh264()`), instead of asking.
- WebM (VP9) joins the dialog's formats (PNG, MP4, MPG, MOV, GIF today), and WebM and animated GIF work everywhere through the same ffmpeg.
- A clear message when encoding fails, naming the encoder and the reason, instead of ffmpeg's raw output alone.

**Approaches considered.**

- **A. The operating system's H.264 encoder (chosen for Windows and macOS).** An LGPL ffmpeg with `h264_mf` and `h264_videotoolbox`; patents covered by the operating system; fast; plays everywhere. Linux has no such encoder (VAAPI needs suitable hardware and drivers).
- **B. Cisco's OpenH264 (chosen for Linux).** Cisco pays the patent fees only for the binary it distributes itself, so PyMOL+ downloads it from Cisco after asking and never ships it.
- C. GPL ffmpeg with x264. Best quality, but GPL code and the H.264 patent question in the app package, and a change to the licence Hannah decided. Rejected.

**Decisions made with the developer.**

- Movies are mainly for talks: H.264 in `.mp4` is the target.
- A on Windows and macOS, B on Linux.
- FFmpeg is built once per version by a separate workflow `ffmpeg.yaml` for Windows x64, macOS arm64 and x86_64 and Linux x86_64 (glibc 2.28), and published as assets of a release in this repository (tag `ffmpeg-<version>-<build>`, e.g. `ffmpeg-7.1.1-1`); Bazel fetches them pinned by checksum (reviewer question, accepted 2026-11-23).
- That release also carries the exact FFmpeg source tarball, the patches and the configure lines, as the LGPL requires; the app's licence files point to it (reviewer question, accepted 2026-11-23).

**Calls made in the design (Claude's, open to correction).**

- The ffmpeg build is LGPL only (`--disable-gpl --disable-nonfree`), with only the encoders, muxers and filters `movie.produce` needs, to keep it small.
- The app's licence expression `BSD-3-Clause AND LGPL-3.0-only AND HPND` stays: FFmpeg's LGPL-2.1-or-later is covered by LGPL-3.0-only; its licence text and a pointer to the exact source (as the LGPL requires) join the bundle's licence files.
- The bundled ffmpeg is appended to the **end** of the `PATH` in the app's `startup_wrapper.py` (`distribution/edited/pymol/`), so an ffmpeg the user installed still wins. Whichever ffmpeg is found, the edited `movie.py` asks it for its encoders (`ffmpeg -encoders`) and picks the best H.264 one it has: `libx264`, then `h264_mf` or `h264_videotoolbox`, then `libopenh264`; only when none is available does the OpenH264 question come up.
- `h264_videotoolbox` runs with `-allow_sw 1`, so machines and virtual machines without the hardware encoder (GitHub's macOS runners among them) fall back to Apple's software encoder.
- `.mov` gets the same H.264 choice as `.mp4`.
- The Export Movie dialog (`modules/pmg_qt/file_dialogs.py`, `movieexport.ui`) gets app copies under `distribution/edited/pmg_qt/` with marked edits for WebM, the OpenH264 question and the checkbox; the question is asked there on the GUI thread, never from `produce`, which runs `_encode` on a background thread.
- Edited copies of `movie.py` and the dialog are used because the encoder choice sits inside `_encode`; ADR 0001's preference for `pymol3` code is kept for the OpenH264 download and cache, which live in a new `pymol3.movie` module.
- The OpenH264 download is pinned to one Cisco release, checked by its SHA-256, stored in the user's cache folder, and asked for once; the answer is remembered in the app's `QSettings`.
- Quality: PyMOL's `quality` setting (0–100) maps to each encoder's own quality or bitrate option, since `-crf` is x264's alone.
- Video is H.264, `yuv420p`, `+faststart`, so it streams and plays in PowerPoint and Keynote; `produce` already rounds width and height down to even numbers for `.mp4`, `.mov` and `.webm`.

**Facts from the code that bind the design.**

- `movie.produce` (`modules/pymol/movie.py`) finds encoders with `shutil.which` (`find_exe`), guesses `ffmpeg` when present, and for `.mp4` passes no codec but x264's `-crf`; without x264, ffmpeg would pick MPEG-4 Part 2, which PowerPoint plays poorly. So the encoder must be chosen explicitly: the edit goes into an app copy of `movie.py` under `distribution/edited/pymol/`, marked like the GUI's edits, and `//distribution/edited:edited_base_test` watches its upstream original.
- `distribution/edited/pymol/startup_wrapper.py` already prepares the environment (for example `SSL_CERT_FILE`) before PyMOL starts, on every platform (on Linux through `pymol_app_start`).
- `_encode` runs a bare `ffmpeg` from the `PATH`; `encoder` accepts only `ffmpeg`, `convert` and `mpeg_encode`, no path.
- The edited copies reach the app through the bundle's `overlays`; `//distribution/edited:edited_base_test` today checks only `edited/pmg_qt/*.py` against `//modules/pmg_qt`, so it is extended to `movie.py` (and `upstream.sha256` gains its line), without requiring one for `startup_wrapper.py`.
- No ready-made LGPL ffmpeg fits: BtbN's LGPL builds (Windows, glibc 2.28 Linux) link their own OpenH264 build and other extras, macOS has no LGPL build, and stock FFmpeg cannot load `libopenh264` later. FFmpeg is built from source for all platforms, Linux with a small loader stub (as Fedora's `noopenh264`) so it starts without OpenH264; `linux_libraries_test` catches a build that needs it at start.

## Global Constraints

Quoted from AGENTS.md:

- "App package and AppStream license: `BSD-3-Clause AND LGPL-3.0-only AND HPND`"; no GPL code in the bundle.
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`); when a `modules/` original changes, `//distribution/edited:edited_base_test` fails until the edits are ported and `distribution/edited/upstream.sha256` is updated."
- "New dependency versions only when they are at least 14 days old."
- macOS minimum 12.0 and one DMG per architecture; Linux binaries need at most glibc 2.28 (from `features/app-bazel-build.md`).
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only." The `ffmpeg.yaml` workflow runs by hand (`workflow_dispatch`) and on its own tags, never on pull requests.
- Releases are made by the owners: `ffmpeg.yaml` creates a draft release that Martin or Hannah publishes.

## Scope

MODULE.bazel
MODULE.bazel.lock
distribution/BUILD.bazel
distribution/bundle/**
distribution/edited/**
distribution/linux/**
distribution/macos/**
distribution/windows/**
distribution/tests/**
distribution/licenses/**
tools/bazel/**
modules/pymol3/**
tests/pymol3_*/**
.github/workflows/**

## Done

Both steps below are merged into `production`, and a fresh install on Windows, macOS (both architectures) and Linux exports an MP4 that plays in PowerPoint or Keynote.

## Non-goals

- GPL encoders (x264, x265) or any H.264 encoder PyMOL+ would distribute itself.
- HEVC, AV1 or ProRes output.
- A new movie export dialog; the existing one only gains WebM and the OpenH264 checkbox.
- Changes to the wheel: `pymol-open-source-whl` keeps looking for a user-installed ffmpeg.
- Hardware encoding on Linux (VAAPI, NVENC).

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts.

1. **ffmpeg build and bundle** (`mp4-export-ffmpeg`): the `ffmpeg.yaml` workflow that builds the LGPL ffmpeg per platform (Windows x64 with Media Foundation, through MinGW; macOS arm64 and x86_64 with VideoToolbox, macOS 12 minimum; Linux x86_64 in `manylinux_2_28` with OpenH264 behind a loader stub, plus libvpx) and publishes binaries, source, patches and configure lines as one release; the pinned `http_archive`s in `MODULE.bazel`; its licence and source pointer in the bundle; the `PATH` entry in `startup_wrapper.py`; bundle tests that run `ffmpeg -encoders` and check the expected encoders and the absence of GPL ones (`ffmpeg -L`, `--enable-gpl` not in its configuration).
2. **Encoder choice and the OpenH264 download** (`mp4-export-encoders`): the marked edit in the app copy of `movie.py` (explicit encoder per platform, quality mapping, even dimensions, `+faststart`, clear errors), and on Linux the one-time question, the pinned download from Cisco with SHA-256 check, the cache and the WebM/GIF fallback.

## Review Focus

- **ffmpeg on Linux needing OpenH264 at start.** An ffmpeg linked against `libopenh264` fails to start without it, which would break WebM and GIF too. Covered by a bundle test that runs the Linux ffmpeg in a clean container without OpenH264 and encodes WebM.
- **The user's own ffmpeg.** A user ffmpeg without any H.264 encoder must not end in MPEG-4 Part 2. Covered by tests of the encoder choice against `ffmpeg -encoders` listings with and without `libx264`, `h264_mf`, `h264_videotoolbox` and `libopenh264`.
- **Asking from the wrong thread.** The OpenH264 question must never come from `produce`. Covered by a headless test that exports MP4 without an encoder and gets the message.
- **The macOS minimum and glibc 2.28.** A prebuilt ffmpeg may need a newer macOS or glibc. Covered by the existing bundle checks, which must include the ffmpeg binary.
- **A GPL build slipping in.** Covered by the bundle test on `ffmpeg -L` and the configuration line.

## Acceptance criteria

- On fresh installs on Windows and macOS (both architectures), Export Movie As… `.mp4` writes H.264 (`yuv420p`) that plays in PowerPoint and Keynote, without any download.
- On Linux (and Windows N), the first MP4 export asks once in the dialog; Download fetches OpenH264 from Cisco, checks it, and exports; Not now offers WebM or GIF; the answer is remembered and can be changed with the dialog's checkbox; Cisco's credit is in the About box and the licence files.
- `.mov` exports carry H.264 too; a user-installed ffmpeg on the `PATH` is used first.
- WebM and GIF export work on all platforms without a download.
- `quality` changes the file size and quality noticeably on every encoder.
- The bundle contains no GPL code; FFmpeg's licence and source pointer are in the bundle's licence files; the app's licence expression is unchanged.
- `bazel test //distribution/...` passes on every platform, `edited_base_test` included.

## Verification

- A run of `ffmpeg.yaml` produces the draft release with binaries for all four platforms, the source tarball, the patches and the configure lines.
- `bazel test //distribution/...` on Windows, macOS (arm64, x86_64) and Linux: the ffmpeg encoder and licence checks, the architecture, macOS 12 and glibc 2.28 checks including ffmpeg, the headless smoke test exporting a short MP4 (Windows, macOS) and WebM (all).
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand: an exported MP4 inserted into PowerPoint on Windows and Keynote on macOS, played in presentation mode; on Linux the download question, the download and an MP4 that plays in LibreOffice Impress and a browser.
