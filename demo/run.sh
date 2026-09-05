#!/usr/bin/env bash
# build the demo and serve it on 127.0.0.1:8080
#
# usage: ./run.sh [config.toml]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

config="${1:-hedge.toml}"

if ! command -v mach >/dev/null 2>&1; then
    echo "run.sh: the mach compiler is not on PATH" >&2
    exit 1
fi

# the demo is its own Mach project with its own pinned dependencies, so it does
# not inherit the parent repository's dep/ directory
if [ ! -d dep/hedge ]; then
    echo "run.sh: fetching dependencies"
    mach dep pull
fi

echo "run.sh: building"
mach build . --profile release

binary="out/linux-x86_64/release/bin/laurel-demo"
if [ ! -x "$binary" ]; then
    # the artifact lands under the host target directory; find it if the name
    # above does not match this machine
    binary="$(find out -type f -name laurel-demo -perm -u+x | head -n 1)"
fi
if [ -z "$binary" ] || [ ! -x "$binary" ]; then
    echo "run.sh: the demo binary was not produced" >&2
    exit 1
fi

echo "run.sh: starting $binary $config"
exec "$binary" "$config"
