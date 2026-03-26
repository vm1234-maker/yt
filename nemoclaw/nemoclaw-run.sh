#!/usr/bin/env sh
# Launcher so the CLI always uses the venv created by install-to-sandbox.sh
# OpenShell sets HTTP_PROXY; host.docker.internal must bypass it or Next calls get 403.
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}host.docker.internal,192.168.5.2"
exec /sandbox/.venvs/nemo/bin/python /sandbox/.openclaw/nemoclaw_cli.py "$@"
