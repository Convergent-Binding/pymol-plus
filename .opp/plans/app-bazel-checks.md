# Quick Checks with Bazel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `bazel run //distribution:checks` runs ruff, ShellCheck and actionlint, at the versions pinned today, on the checkout. These are the checks `uvx pre-commit run --all-files` runs now. The CI job `checks` runs it, and pre-commit and its Dependabot entry go.

**Architecture:**
- The three tools come as wheels from a new locked hub, `@app_checks_pip`. rules_python puts each wheel's own program into the wheel repository's `bin/`, exposed as `@app_checks_pip//<package>:data`.
- A small `py_binary`, `//distribution/checks`, finds the three programs through the runfiles library (`$(rlocationpaths ...)`), so it works on Windows without runfiles links too. It then runs them on the workspace (`BUILD_WORKSPACE_DIRECTORY`):
  - **ruff check:** in `distribution/`, with its `pyproject.toml` settings and file discovery.
  - **ShellCheck:** on the tracked shell scripts under `distribution/`, as pre-commit selected them: `.sh`/`.bash` or a `sh`/`bash` shebang, and no `.zsh`.
  - **actionlint:** on the repository's workflows, with ShellCheck on its `PATH` for the `run:` scripts.
- It exits non-zero if any tool reports a finding. `--fix` hands ruff's fixes on.
- `//distribution:checks` is an alias for it.

**Tech Stack:** Bazel 9, rules_python 2.3.2 (`pip.parse`, the uv `lock` rule, the runfiles library), ruff 0.17.4, shellcheck-py 0.11.0.1, actionlint-py 1.7.12.25.

**Spec:** `.opp/plans/features/app-bazel-build.md`, step 6. The developer chose `bazel run` on the checkout over a cached `bazel test`: always complete, no file lists to keep in BUILD files, and ruff's fixes can be applied.

## Parent

`features/app-bazel-build.md`, step 6: Quick checks.

## Global Constraints

- The tool versions stay those of `distribution/.pre-commit-config.yaml`: ruff 0.17.4, shellcheck-py 0.11.0.1, actionlint-py 1.7.12.25. New versions come later through Dependabot's pip entry, with its 14-day cooldown.
- ruff keeps the app's settings in `distribution/pyproject.toml` (2-space indent, isort, `edited/` excluded). It checks the app's Python files only, not the PyMOL wheel's sources.
- ShellCheck checks the files pre-commit's `shellcheck` hook selected under `distribution/`. `.zsh` stays excluded.
- desktop-file-validate and appstreamcli stay a step of the `checks` job. They are Ubuntu system packages with no wheels.
- The check runs on Windows, macOS and Linux (`bazel run` from any folder of the repository).
- Python follows the opp family style and passes the app's ruff settings.

## Review Focus

- A tool program not found on one platform: Windows wheels name it `ruff.exe`, and a runfiles path that works on Linux may not exist on Windows, which has no runfiles links. Task 2's test locates and runs each program's `--version` in `bazel test //distribution/...`, which `bazel.yaml` runs on all four platforms.
- A check that passes because it checked nothing: an empty file list or a wrong working folder. The checker prints how many files each tool checked, and Task 2's test runs it on a fixture tree with one finding per tool.
- actionlint without ShellCheck on its `PATH` silently skips the `run:` scripts. That is why pre-commit gave it `shellcheck-py` as an extra dependency. The checker puts ShellCheck's folder first on `PATH`, and Task 2's fixture has a `run:` script with a ShellCheck finding.
- Workflows actionlint did not check before: pre-commit checked only `build_app.yaml` and `docs.yaml`. Task 3 runs it on all of `.github/workflows/` and fixes what it finds.

## Scope

```
MODULE.bazel
distribution/BUILD.bazel
distribution/checks/**
distribution/checks_requirements.in
distribution/checks_requirements_lock.txt
distribution/.pre-commit-config.yaml
.github/dependabot.yml
.github/workflows/*.yaml
distribution/README.md
AGENTS.md
.opp/plans/features/app-bazel-build.md
```

## Done

The CI job `checks` runs `bazel run //distribution:checks` and the desktop and AppStream validation, and passes. `distribution/.pre-commit-config.yaml` and Dependabot's `pre-commit` entry are gone. `bazel test //distribution/...` runs the checker's tests on all four platforms. All of this is on a pull request into `bazel-app-packaging`.

## Non-goals

- A cached, hermetic `bazel test` over the checked files (the developer chose `bazel run`).
- `ruff format`, or new rules or tools beyond today's three.
- Checking the PyMOL wheel's sources, or the root's Python, with ruff. The opp style check (`.opp/style/check.py`) covers changed lines.
- The website (step 5, skipped; it needs an overhaul of its own) and removing cx_Freeze (step 7).

## Interfaces

- `bazel run //distribution:checks [-- --fix]`: runs the three tools on the workspace. It exits 0 when all pass, and otherwise 1 after running all three.
- `bazel run //distribution:checks_requirements.update`: relocks `checks_requirements.in`.
- `distribution/checks/checks.py` exports:
  - `shell_scripts(root, paths) -> list[pathlib.Path]`, pre-commit's selection;
  - `tool(name) -> pathlib.Path`, a program found through the runfiles;
  - `main(argv) -> int`.

## Tasks

### Task 1: The locked tool hub

- [ ] `distribution/checks_requirements.in` pins `ruff==0.17.4`, `shellcheck-py==0.11.0.1` and `actionlint-py==1.7.12.25`. A `lock` target `checks_requirements` in `distribution/BUILD.bazel` (like `build_requirements`: `--universal`, Python 3.13) writes `checks_requirements_lock.txt`. Run it.
- [ ] `MODULE.bazel`: `pip.parse(hub_name = "app_checks_pip", python_version = "3.13", requirements_lock = "//distribution:checks_requirements_lock.txt")` and `use_repo`.
- [ ] Confirm that `@app_checks_pip//ruff:data`, `//shellcheck_py:data` and `//actionlint_py:data` hold `bin/ruff[.exe]`, `bin/shellcheck[.exe]` and `bin/actionlint[.exe]` on Windows (`bazel cquery --output=files`). If a wheel puts its program elsewhere, the checker looks it up by file name within that target's files.

### Task 2: The checker, test first

- [ ] `distribution/checks/tests/checks_test.py` (`py_test`, all platforms):
  - `shell_scripts` selects `.sh`, `.bash` and `#!/bin/sh`, `#!/usr/bin/env bash` files, and skips `.zsh` and other files;
  - `tool()` finds each of the three programs, and each runs `--version`;
  - `main` on a fixture tree, with one ruff, one ShellCheck and one actionlint `run:` finding, returns 1 and names all three;
  - `main` on a clean tree returns 0.
- [ ] `distribution/checks/checks.py`:
  - It finds the workspace: `BUILD_WORKSPACE_DIRECTORY`, or `--root` for the tests.
  - It lists tracked files with `git ls-files`, with a fallback to walking the tree when git is missing.
  - It runs ruff (`check`, cwd `distribution/`, plus `--fix` when asked), ShellCheck on `shell_scripts`, and actionlint with cwd the root and ShellCheck's folder first on `PATH`.
  - It prints each tool's file count and result, runs all three, and returns 1 if any failed.
- [ ] `distribution/checks/BUILD.bazel`: `py_binary` `checks` with `data` the three `:data` targets and `args` their `$(rlocationpaths ...)`, and the test. `distribution/BUILD.bazel`: `alias(name = "checks", actual = "//distribution/checks")`.

### Task 3: Run it on the repository, and switch CI

- [ ] `bazel run //distribution:checks` on the branch. It reports the same as `uvx pre-commit run --all-files`: clean, except for workflows actionlint did not check before. Fix those findings.
- [ ] `.github/workflows/build_app.yaml`, job `checks`: setup-bazel (as the other jobs) and `bazel run //distribution:checks` replace setup-uv, the pre-commit cache and the pre-commit run. The desktop and AppStream step stays.
- [ ] Delete `distribution/.pre-commit-config.yaml` and Dependabot's `pre-commit` entry. Dependabot's pip entry for `/distribution` now also proposes the check tools' versions.

### Task 4: Docs

- [ ] AGENTS.md "App checks", `distribution/README.md` "Quick checks" and the comments in `build_app.yaml`: `bazel run //distribution:checks` (with `-- --fix`) replaces `uvx pre-commit`.
- [ ] The feature plan already records step 5 as skipped and step 6 as `bazel run` (committed with this plan).

## Acceptance criteria

- `bazel run //distribution:checks` passes on the branch on Windows, and in CI's `checks` job on Ubuntu. On a planted finding of each kind it fails and names the file.
- `bazel test //distribution/...` runs `checks_test` on Windows, macOS (both architectures) and Linux in `bazel.yaml`, and it passes.
- No pre-commit configuration, pre-commit run or Dependabot `pre-commit` entry is left. `git grep -n pre-commit` finds only history notes, if any.
- The tool versions are those pinned today.

## Verification

- `bazel test //distribution/...` (Windows, locally).
- `bazel run //distribution:checks`, and `bazel run //distribution:checks -- --fix` on a planted fixable ruff finding.
- `python3 .opp/style/check.py --base origin/bazel-app-packaging`.
- CI on the pull request: `checks`, `bazel.yaml` on all four platforms, and the app jobs.
