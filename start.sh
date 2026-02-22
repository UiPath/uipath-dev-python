#!/bin/sh
/root/.local/bin/uv venv --clear
. ./.venv/bin/activate
/root/.local/bin/uv sync
/root/.local/bin/uv run uipath-dev-server
