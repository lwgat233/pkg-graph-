#!/bin/bash
# depmap dnf resolver — query RHEL/Fedora package dependencies
# Usage: dnf-deps.sh <pkgname> [--build] [--recommends] [--suggests] [--conflicts]
# Works with dnf and falls back to yum

set -euo pipefail

PKG="$1"
shift

# Detect package manager
if command -v dnf &>/dev/null; then
    PM="dnf"
elif command -v yum &>/dev/null; then
    PM="yum"
else
    echo '{"error": "no dnf or yum found"}' >&2
    exit 1
fi

WANT_DEPENDS=1
WANT_BUILD=0
WANT_RECOMMENDS=0
WANT_SUGGESTS=0
WANT_CONFLICTS=0

for arg in "$@"; do
    case "$arg" in
        --build)      WANT_BUILD=1 ;;
        --recommends) WANT_RECOMMENDS=1 ;;
        --suggests)   WANT_SUGGESTS=1 ;;
        --conflicts)  WANT_CONFLICTS=1 ;;
    esac
done

echo "{"
echo "  \"name\": \"$PKG\","

# Version
VER=$($PM info "$PKG" 2>/dev/null | grep -E '^Version' | head -1 | awk '{print $3}' || echo "unknown")
echo "  \"version\": \"$VER\","

# Depends (requires)
echo -n "  \"depends\": ["
if [ "$WANT_DEPENDS" = 1 ]; then
    DEPS=$($PM repoquery --requires --resolve "$PKG" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')
    FIRST=true
    IFS=',' read -ra DEP_ARR <<< "$DEPS"
    for dep in "${DEP_ARR[@]}"; do
        dep=$(echo "$dep" | xargs)
        [ -z "$dep" ] && continue
        [ "$FIRST" = true ] && FIRST=false || echo -n ", "
        echo -n "\"$dep\""
    done
fi
echo "],"

# Build-Depends
echo -n "  \"build-depends\": []"
echo ","

# Recommends
echo -n "  \"recommends\": ["
if [ "$WANT_RECOMMENDS" = 1 ]; then
    RECS=$($PM repoquery --recommends "$PKG" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')
    FIRST=true
    IFS=',' read -ra REC_ARR <<< "$RECS"
    for rec in "${REC_ARR[@]}"; do
        rec=$(echo "$rec" | xargs)
        [ -z "$rec" ] && continue
        [ "$FIRST" = true ] && FIRST=false || echo -n ", "
        echo -n "\"$rec\""
    done
fi
echo "],"

# Suggests
echo -n "  \"suggests\": ["
if [ "$WANT_SUGGESTS" = 1 ]; then
    SUGS=$($PM repoquery --suggests "$PKG" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')
    FIRST=true
    IFS=',' read -ra SUG_ARR <<< "$SUGS"
    for sug in "${SUG_ARR[@]}"; do
        sug=$(echo "$sug" | xargs)
        [ -z "$sug" ] && continue
        [ "$FIRST" = true ] && FIRST=false || echo -n ", "
        echo -n "\"$sug\""
    done
fi
echo "],"

# Conflicts
echo -n "  \"conflicts\": ["
if [ "$WANT_CONFLICTS" = 1 ]; then
    CONFS=$($PM repoquery --conflicts "$PKG" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')
    FIRST=true
    IFS=',' read -ra CONF_ARR <<< "$CONFS"
    for conf in "${CONF_ARR[@]}"; do
        conf=$(echo "$conf" | xargs)
        [ -z "$conf" ] && continue
        [ "$FIRST" = true ] && FIRST=false || echo -n ", "
        echo -n "\"$conf\""
    done
fi
echo "],"

echo "  \"system\": \"$PM\""
echo "}"
