#!/usr/bin/env bash

set -euo pipefail

mode=check
case "${1:-}" in
  "") ;;
  --check) mode=check ;;
  --print) mode=print ;;
  --install) mode=install ;;
  -h|--help)
    cat <<'EOF'
Usage: install-linux-dependencies.sh [--check|--print|--install]

  --check    Report missing shared libraries without changing the system.
  --print    Print the package set for the detected package manager.
  --install  Install the package set, then check the shared libraries again.
EOF
    exit 0
    ;;
  *)
    echo "Unknown option: $1" >&2
    exit 2
    ;;
esac

required_libraries=(
  libX11.so.6
  libXcomposite.so.1
  libXdamage.so.1
  libXext.so.6
  libXfixes.so.3
  libXrandr.so.2
  libasound.so.2
  libatk-1.0.so.0
  libatk-bridge-2.0.so.0
  libatspi.so.0
  libcairo.so.2
  libcups.so.2
  libcurl.so.4
  libdbus-1.so.3
  libexpat.so.1
  libgbm.so.1
  libgtk-3.so.0
  libnspr4.so
  libnss3.so
  libpango-1.0.so.0
  libudev.so.1
  libxcb.so.1
  libxkbcommon.so.0
  libxkbfile.so.1
)

apt_packages=(
  ca-certificates libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0
  libcairo2 libcups2 libcurl4 libdbus-1-3 libexpat1 libgbm1 libglib2.0-0
  libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libstdc++6 libudev1 libx11-6
  libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0
  libxkbfile1 libxrandr2 xdg-utils
)

rpm_packages=(
  ca-certificates alsa-lib at-spi2-atk at-spi2-core atk cairo cups-libs
  libcurl dbus-libs expat mesa-libgbm glib2 gtk3 nspr nss pango libstdc++
  systemd-libs libX11 libxcb libXcomposite libXdamage libXext libXfixes
  libxkbcommon libxkbfile libXrandr xdg-utils
)

emerge_packages=(
  app-misc/ca-certificates media-libs/alsa-lib app-accessibility/at-spi2-core
  x11-libs/cairo net-print/cups net-misc/curl sys-apps/dbus dev-libs/expat
  media-libs/mesa dev-libs/glib x11-libs/gtk+ dev-libs/nspr dev-libs/nss
  x11-libs/pango virtual/libudev x11-libs/libX11 x11-libs/libxcb
  x11-libs/libXcomposite x11-libs/libXdamage x11-libs/libXext
  x11-libs/libXfixes x11-libs/libxkbcommon x11-libs/libxkbfile
  x11-libs/libXrandr x11-misc/xdg-utils
)

manager=
packages=()
if command -v apt-get >/dev/null 2>&1; then
  manager=apt
  packages=("${apt_packages[@]}")
elif command -v dnf >/dev/null 2>&1; then
  manager=dnf
  packages=("${rpm_packages[@]}")
elif command -v yum >/dev/null 2>&1; then
  manager=yum
  packages=("${rpm_packages[@]}")
elif command -v emerge >/dev/null 2>&1; then
  manager=emerge
  packages=("${emerge_packages[@]}")
else
  echo "No supported package manager found (apt-get, dnf, yum, or emerge)." >&2
  exit 2
fi

print_packages() {
  printf '%s\n' "${packages[@]}"
}

check_libraries() {
  local cache
  local missing=0
  if ! command -v ldconfig >/dev/null 2>&1; then
    echo "ldconfig is required to check installed shared libraries." >&2
    return 2
  fi
  cache="$(ldconfig -p 2>/dev/null || true)"
  for library in "${required_libraries[@]}"; do
    if ! grep -Fq "$library " <<<"$cache"; then
      echo "Missing: $library"
      missing=1
    fi
  done
  if [ "$missing" -eq 0 ]; then
    echo "All baseline Sprouted Code shared libraries are available."
  fi
  return "$missing"
}

if [ "$mode" = print ]; then
  echo "Package manager: $manager"
  print_packages
  exit 0
fi

if [ "$mode" = install ]; then
  elevate=()
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || {
      echo "Run as root or install sudo before using --install." >&2
      exit 2
    }
    elevate=(sudo)
  fi

  case "$manager" in
    apt)
      "${elevate[@]}" apt-get update
      "${elevate[@]}" apt-get install -y "${packages[@]}"
      ;;
    dnf|yum)
      "${elevate[@]}" "$manager" install -y "${packages[@]}"
      ;;
    emerge)
      "${elevate[@]}" emerge --noreplace "${packages[@]}"
      ;;
  esac
fi

check_libraries
