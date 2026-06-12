#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
TOPDIR="${TOPDIR:-$HOME/rpmbuild}"
BUILD_MODE="binary"
CLEAN=0
GST_VERSION="${GST_VERSION:-}"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --srpm-only             Build source RPM only
  --binary                Build binary RPM from generated SRPM (default)
  --clean                 Remove this package from BUILD/BUILDROOT before building
  --topdir DIR            RPM topdir (default: \$HOME/rpmbuild)
  --gstreamer-version VER GStreamer package version dependency
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --srpm-only)
      BUILD_MODE="srpm"
      ;;
    --binary)
      BUILD_MODE="binary"
      ;;
    --clean)
      CLEAN=1
      ;;
    --topdir)
      TOPDIR="$2"
      shift
      ;;
    --gstreamer-version)
      GST_VERSION="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required tool: $1" >&2
    exit 1
  fi
}

project_version() {
  local dir="$1"
  sed -n "s/^[[:space:]]*version[[:space:]]*:[[:space:]]*'\\([^']*\\)'.*/\\1/p" "$dir/meson.build" | head -n 1
}

release_from_git() {
  local desc count short

  desc="$(git -C "$PROJECT_DIR" describe --tags --long --always HEAD)"
  short="$(git -C "$PROJECT_DIR" rev-parse --short=7 HEAD)"

  if [[ "$desc" =~ -([0-9]+)-g[0-9a-f]+$ ]]; then
    count="${BASH_REMATCH[1]}"
  else
    count="1"
  fi

  if [[ "$count" == "0" ]]; then
    printf '1'
  else
    printf '%s.git%s' "$count" "$short"
  fi
}

require_tool git
require_tool rpmbuild
require_tool sed

if [[ -z "$GST_VERSION" && -f "$WORKSPACE_DIR/gstreamer/meson.build" ]]; then
  GST_VERSION="$(project_version "$WORKSPACE_DIR/gstreamer")"
fi

if [[ -z "$GST_VERSION" ]]; then
  echo "Set GST_VERSION or pass --gstreamer-version so libcamera can depend on the matching gstreamer RPM" >&2
  exit 1
fi

mkdir -p "$TOPDIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,tmp}

name="libcamera"
version="$(project_version "$PROJECT_DIR")"
release="$(release_from_git)"
commit="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
shortcommit="$(git -C "$PROJECT_DIR" rev-parse --short=7 HEAD)"
spec="$PROJECT_DIR/packaging/rpm/libcamera.spec"
archive="$TOPDIR/SOURCES/${name}-${commit}.tar.gz"

if [[ -z "$version" ]]; then
  echo "Could not determine libcamera version from meson.build" >&2
  exit 1
fi

echo "==> $name $version-$release ($shortcommit), gstreamer dependency $GST_VERSION"
git -C "$PROJECT_DIR" archive --format=tar.gz --prefix="${name}-${commit}/" -o "$archive" "$commit"

if [[ "$CLEAN" == "1" ]]; then
  rm -rf "$TOPDIR/BUILD/${name}-"* "$TOPDIR/BUILDROOT/${name}-"*
fi

rpmbuild -bs \
  --define "_topdir $TOPDIR" \
  --define "_tmppath $TOPDIR/tmp" \
  --define "__brp_add_determinism /bin/true" \
  --define "project_version $version" \
  --define "snapshot_release $release" \
  --define "commit $commit" \
  --define "shortcommit $shortcommit" \
  --define "gst_version $GST_VERSION" \
  "$spec"

if [[ "$BUILD_MODE" == "binary" ]]; then
  srpm="$(find "$TOPDIR/SRPMS" -maxdepth 1 -name "${name}-${version}-${release}"'*.src.rpm' -print | sort | tail -n 1)"
  if [[ -z "$srpm" ]]; then
    echo "Could not find generated SRPM for $name" >&2
    exit 1
  fi
  rpmbuild --rebuild \
    --define "_topdir $TOPDIR" \
    --define "_tmppath $TOPDIR/tmp" \
    --define "__brp_add_determinism /bin/true" \
    "$srpm"
fi

echo
echo "SRPMs: $TOPDIR/SRPMS"
echo "RPMs:  $TOPDIR/RPMS"
