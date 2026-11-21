#!/usr/bin/env bash
# Downloads files of the latest published app release for the update tests: the
# newest published (not draft, not pre-release) release with a setup-v* tag in
# this repository. Releases with other tags belong to the PyMOL wheel. While this
# repository has no app release yet, it takes the latest release of the former
# repository kullik01/pymol-open-source-setup.
#
# Usage: tests/download_previous_release.sh <directory> <file pattern>...
# e.g.   tests/download_previous_release.sh previous '*.deb' '*.rpm'
# Needs GH_TOKEN and GITHUB_REPOSITORY, which GitHub Actions provides.
set -euo pipefail

FORMER_REPOSITORY="kullik01/pymol-open-source-setup"

if [ $# -lt 2 ]; then
  echo "Usage: $0 <directory> <file pattern>..." >&2
  exit 2
fi
DIR="$1"
shift
PATTERNS=()
for PATTERN in "$@"; do
  PATTERNS+=(--pattern "$PATTERN")
done

# gh lists the newest release first
TAG="$(gh release list --repo "$GITHUB_REPOSITORY" --exclude-drafts --exclude-pre-releases --limit 100 \
  --json tagName --jq '[.[] | select(.tagName | startswith("setup-v"))][0].tagName // empty')"
if [ -n "$TAG" ]; then
  echo "Latest app release: ${TAG} (${GITHUB_REPOSITORY})"
  gh release download "$TAG" --repo "$GITHUB_REPOSITORY" --dir "$DIR" "${PATTERNS[@]}"
else
  echo "${GITHUB_REPOSITORY} has no app release yet; taking the latest release of ${FORMER_REPOSITORY}"
  gh release download --repo "$FORMER_REPOSITORY" --dir "$DIR" "${PATTERNS[@]}"
fi
