#!/bin/sh
# Usage: ./run.sh -p PACKAGE [options]
# Tests: ./run.sh test
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$1" = "test" ]; then
    cd "$DIR" && exec python3 -m unittest discover -s tests -t . -v
fi
exec python3 "$DIR/src/main.py" "$@"
