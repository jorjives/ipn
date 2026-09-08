#!/bin/sh
# Builds docs/ with the image GitHub Pages itself uses, into /tmp/oidl-out. Needs Docker and gh.
#   scripts/site_build.sh [true]     # true for verbose Jekyll output
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p /tmp/oidl-out  # Jekyll cleans it; the files are root-owned after a run
docker run --rm -v "$ROOT/docs:/work/src:ro" -v /tmp/oidl-out:/work/out \
  -e GITHUB_WORKSPACE=/work -e INPUT_SOURCE=src -e INPUT_DESTINATION=out -e INPUT_FUTURE=false \
  -e INPUT_BUILD_REVISION=HEAD -e INPUT_VERBOSE="${1:-false}" -e INPUT_TOKEN="$(gh auth token)" \
  -e PAGES_REPO_NWO=jorjives/ipn -e GITHUB_REPOSITORY=jorjives/ipn \
  ghcr.io/actions/jekyll-build-pages:v1.0.13 2>&1 | grep -v "^\s*from " | grep -v "faraday-retry"
