#!/usr/bin/env bash
# macOS: double-click this file to start the app. First run installs everything it needs.
cd "$(dirname "$0")" || exit 1
bash start.sh
status=$?
if [ "$status" -ne 0 ]; then
  echo
  read -r -p "Something went wrong (see above). Press Return to close this window." _
fi
