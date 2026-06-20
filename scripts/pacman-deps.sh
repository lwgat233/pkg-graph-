#!/bin/bash
# depmap pacman resolver — query Arch Linux package dependencies
# Usage: pacman-deps.sh <pkgname> [--build] [--recommends] [--suggests] [--conflicts]
# Parses local pacman sync database (offline)

set -euo pipefail

PKG="$1"
shift

WANT_DEPENDS=1
WANT_BUILD=0
WANT_OPTDEPS=0
WANT_CONFLICTS=0

for arg in "$@"; do
    case "$arg" in
        --build)     WANT_BUILD=1 ;;
        --recommends|--suggests) WANT_OPTDEPS=1 ;;  # pacman uses optional deps for both
        --conflicts) WANT_CONFLICTS=1 ;;
    esac
done

echo "{"
echo "  \"name\": \"$PKG\","

# Version
VER=$(pacman -Qi "$PKG" 2>/dev/null | grep -E '^Version' | awk '{print $3}' || echo "unknown")
echo "  \"version\": \"$VER\","

# Depends
echo -n "  \"depends\": ["
if [ "$WANT_DEPENDS" = 1 ]; then
    DEPS=$(pacman -Qi "$PKG" 2>/dev/null | grep -E '^Depends On' | sed 's/Depends On[[:space:]]*:[[:space:]]*//' | sed 's/  / /g')
    FIRST=true
    if [ -n "$DEPS" ] && [ "$DEPS" != "None" ]; then
        IFS=' ' read -ra DEP_ARR <<< "$DEPS"
        for dep in "${DEP_ARR[@]}"; do
            dep=$(echo "$dep" | sed 's/[><=].*//')  # strip version constraints
            [ -z "$dep" ] && continue
            [ "$FIRST" = true ] && FIRST=false || echo -n ", "
            echo -n "\"$dep\""
        done
    fi
fi
echo "],"

# Build-Depends (makedepends)
echo -n "  \"build-depends\": ["
if [ "$WANT_BUILD" = 1 ]; then
    BDEPS=$(pacman -Qi "$PKG" 2>/dev/null | grep -E '^Build Date' >/dev/null && echo "" || true)
    # Try to get from ABS / PKGBUILD info if available
    # For installed packages, makedepends aren't stored in local DB — query sync DB
    BDEPS=$(pacman -Si "$PKG" 2>/dev/null | grep -E '^Build Depends' | sed 's/Build Depends[[:space:]]*:[[:space:]]*//' || echo "")
    FIRST=true
    if [ -n "$BDEPS" ] && [ "$BDEPS" != "None" ]; then
        IFS=' ' read -ra BDEP_ARR <<< "$BDEPS"
        for dep in "${BDEP_ARR[@]}"; do
            dep=$(echo "$dep" | sed 's/[><=].*//')
            [ -z "$dep" ] && continue
            [ "$FIRST" = true ] && FIRST=false || echo -n ", "
            echo -n "\"$dep\""
        done
    fi
fi
echo "],"

# Optional Deps (== recommends/suggests in pacman world)
echo -n "  \"recommends\": []"
echo ","
echo -n "  \"suggests\": ["
if [ "$WANT_OPTDEPS" = 1 ]; then
    OPTDEPS=$(pacman -Qi "$PKG" 2>/dev/null | grep -E '^Optional Deps' | sed 's/Optional Deps[[:space:]]*:[[:space:]]*//')
    FIRST=true
    while IFS= read -r line; do
        dep=$(echo "$line" | awk '{print $1}' | sed 's/[><=].*//')
        [ -z "$dep" ] && continue
        [ "$FIRST" = true ] && FIRST=false || echo -n ", "
        echo -n "\"$dep\""
    done <<< "$OPTDEPS"
fi
echo "],"

# Conflicts
echo -n "  \"conflicts\": ["
if [ "$WANT_CONFLICTS" = 1 ]; then
    CONFS=$(pacman -Qi "$PKG" 2>/dev/null | grep -E '^Conflicts With' | sed 's/Conflicts With[[:space:]]*:[[:space:]]*//')
    FIRST=true
    if [ -n "$CONFS" ] && [ "$CONFS" != "None" ]; then
        IFS=' ' read -ra CONF_ARR <<< "$CONFS"
        for conf in "${CONF_ARR[@]}"; do
            conf=$(echo "$conf" | sed 's/[><=].*//')
            [ -z "$conf" ] && continue
            [ "$FIRST" = true ] && FIRST=false || echo -n ", "
            echo -n "\"$conf\""
        done
    fi
fi
echo "],"

echo "  \"system\": \"pacman\""
echo "}"
