#!/bin/bash
# pkg-graph apt resolver — query Debian/Ubuntu package dependencies
# Usage: apt-deps.sh <pkgname> [--build] [--recommends] [--suggests] [--conflicts]
# Output: JSON

set -euo pipefail

PKG="$1"
shift

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

# Helper: takes newline-separated list, outputs JSON array
_json_arr() {
    local first=true
    echo -n "["
    while IFS= read -r line; do
        line=$(echo "$line" | xargs)  # trim
        [ -z "$line" ] && continue
        # Skip virtual packages marked with <...>
        [[ "$line" == "<"*">" ]] && continue
        # Escape for JSON
        local escaped="${line//\\/\\\\}"
        escaped="${escaped//\"/\\\"}"
        [ "$first" = true ] && first=false || echo -n ", "
        echo -n "\"$escaped\""
    done
    echo -n "]"
}

# ---- JSON start ----
cat <<EOF
{
  "name": "$PKG",
EOF

# Version
VER=$(dpkg-query -W -f='${Version}' "$PKG" 2>/dev/null || echo "unknown")
echo "  \"version\": \"$VER\","

# Depends
echo -n "  \"depends\": "
if [ "$WANT_DEPENDS" = 1 ]; then
    apt-cache depends "$PKG" 2>/dev/null \
        | grep -E '^\s*Depends:' \
        | sed 's/.*Depends:[[:space:]]*//' \
        | sed 's/[[:space:]]*$//' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//' \
        | grep -v '^$' \
        | _json_arr
else
    echo -n "[]"
fi
echo ","

# Build-Depends
echo -n "  \"build-depends\": "
if [ "$WANT_BUILD" = 1 ]; then
    apt-cache showsrc "$PKG" 2>/dev/null \
        | grep -E '^Build-Depends(-Arch|-Indep)?:' \
        | sed 's/.*Build-Depends[^:]*:[[:space:]]*//' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//; s/([^)]*)//g' \
        | grep -v '^$' \
        | _json_arr
else
    echo -n "[]"
fi
echo ","

# Recommends
echo -n "  \"recommends\": "
if [ "$WANT_RECOMMENDS" = 1 ]; then
    apt-cache depends "$PKG" 2>/dev/null \
        | grep -E '^\s*Recommends:' \
        | sed 's/.*Recommends:[[:space:]]*//' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//' \
        | grep -v '^$' \
        | _json_arr
else
    echo -n "[]"
fi
echo ","

# Suggests
echo -n "  \"suggests\": "
if [ "$WANT_SUGGESTS" = 1 ]; then
    apt-cache depends "$PKG" 2>/dev/null \
        | grep -E '^\s*Suggests:' \
        | sed 's/.*Suggests:[[:space:]]*//' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//' \
        | grep -v '^$' \
        | _json_arr
else
    echo -n "[]"
fi
echo ","

# Conflicts
echo -n "  \"conflicts\": "
if [ "$WANT_CONFLICTS" = 1 ]; then
    apt-cache depends "$PKG" 2>/dev/null \
        | grep -E '^\s*Conflicts:' \
        | sed 's/.*Conflicts:[[:space:]]*//' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//' \
        | grep -v '^$' \
        | _json_arr
else
    echo -n "[]"
fi
echo ","

echo '  "system": "apt"'
echo "}"
