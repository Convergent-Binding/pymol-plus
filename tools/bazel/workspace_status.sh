#!/usr/bin/env bash
# Bazel workspace-status command (see .bazelrc). Feeds PyMOLBuildInfo.h's git
# SHA and date through Bazel's stable-status mechanism instead of a `git` call
# or a clock read inside a build action, neither of which is a declared input.
# The date is the commit's, so an unchanged commit rebuilds nothing.
set -euo pipefail
echo "STABLE_GIT_SHA $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "STABLE_BUILD_DATE $(git log -1 --format=%ct 2>/dev/null || echo 0)"
