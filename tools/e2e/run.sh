#!/bin/sh
# Test the add-on in a real Anki, with the dictionaries built in DIST_DIR (see README.md)
#
# Usage: run.sh ANKI DIST_DIR
#   ANKI: the executable of Anki, e.g. ~/.local/share/AnkiProgramFiles/.venv/bin/anki, or the anki
#   script of an extracted release
set -eu

if [ $# -ne 2 ]; then
    sed -n '2,6s/^# \{0,1\}//p' "$0"
    exit 2
fi
anki=$1
dist=$(realpath "$2")
here=$(dirname "$(realpath "$0")")
repo=$(realpath "$here/../..")
port=${JAPANOTE_E2E_PORT:-18765}
url=http://127.0.0.1:$port

if [ ! -f "$dist/manifest-newer.json" ]; then
    echo "Making a newer version of the dictionaries, to test the update"
    python3 "$here/make_update.py" "$dist" "$url"
fi

base=$(mktemp -d "${TMPDIR:-/tmp}/japanote-e2e.XXXXXX")
echo "Anki base directory: $base"
mkdir -p "$base/addons21/japanote_harness"
# a copy, so that the add-on's user_files do not end up in the repository
cp -r "$repo/japanote" "$base/addons21/japanote"
rm -rf "$base/addons21/japanote/user_files" "$base/addons21/japanote/__pycache__"
cp "$here/harness.py" "$base/addons21/japanote_harness/__init__.py"

# a Python that can import Anki, to create the profile: the one next to Anki, unless given
python=${ANKI_PYTHON:-$(dirname "$anki")/python}
if ! "$python" -c 'import aqt' 2> /dev/null; then
    echo "$python cannot import Anki; set ANKI_PYTHON (see README.md)" >&2
    exit 2
fi
"$python" "$here/make_profile.py" "$base"
manifest=$(basename "$(ls "$dist"/manifest-v*.json)")

python3 "$here/serve.py" "$dist" "$port" 2> "$base/serve.log" &
server=$!
trap 'kill $server' EXIT

# another user name, so that Anki does not find the instance that may already be running
status=0
USER=japanote-test LOGNAME=japanote-test JAPANOTE_MANIFEST_URL="$url/$manifest" QT_QPA_PLATFORM=offscreen \
    timeout 900 "$anki" -b "$base" -p test > "$base/anki.log" 2>&1 || status=$?

cat "$base/harness.log"
if [ $status -ne 0 ]; then
    echo "FAIL: Anki exited with $status (see $base/anki.log)"
fi
if [ $status -ne 0 ] || grep -q '^FAIL' "$base/harness.log" || ! grep -q '^DONE' "$base/harness.log"; then
    exit 1
fi
echo "Passed; screenshots in $base"
