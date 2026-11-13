#!/bin/bash
set -euo pipefail
# Omarchy's package command handles sudo in this visible terminal.
if ! command -v hiddify >/dev/null; then
  if pacman -Si hiddify >/dev/null 2>&1; then
    omarchy pkg add hiddify
  else
    omarchy pkg aur add hiddify
  fi
fi
printf '\nHiddify installed. You can close this terminal.\n'
