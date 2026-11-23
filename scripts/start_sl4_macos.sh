#!/bin/sh
# macOS entry point. No root, NVRAM, EFI, or kernel changes.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then
  exec /usr/bin/python3 "$here/sl4_inventory.py"
fi
exec /usr/bin/python3 "$here/sl4_setup.py" "$@"
