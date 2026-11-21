#!/usr/bin/env bash
# Bazel workspace-status command (see .bazelrc). Feeds PyMOLBuildInfo.h's git
# SHA through Bazel's stable-status mechanism instead of a `git` call inside a
# build action, which would be an undeclared input.
set -euo pipefail
echo "STABLE_GIT_SHA $(git rev-parse HEAD 2>/dev/null || echo unknown)"
