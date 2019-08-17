#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PYTHONPATH=${DIR}:${PYTHONPATH} python3 -m valve_control.relay_controller
