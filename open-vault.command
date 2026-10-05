#!/bin/bash
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then ./.venv/bin/python vault_ui.py; else python3 vault_ui.py; fi
