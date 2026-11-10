#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Instale primeiro conforme README.md: python3.12 -m venv .venv'
  exit 1
fi
exec .venv/bin/python iniciar.py "$@"
