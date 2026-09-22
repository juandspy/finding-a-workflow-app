#!/bin/bash
# Prefix every stdout/stderr line with a local timestamp, then exec the real command.
# Usage: stamp_exec.sh COMMAND [ARGS...]
set -u

stamp() {
  while IFS= read -r line || [ -n "$line" ]; do
    printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$line"
  done
}

if [ "$#" -lt 1 ]; then
  echo "usage: $0 COMMAND [ARGS...]" >&2
  exit 2
fi

# Keep streams separate so launchd StandardOutPath / StandardErrorPath stay useful.
"$@" > >(stamp) 2> >(stamp >&2)
exit $?
