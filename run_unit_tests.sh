#!/usr/bin/env bash
CURA_APP_DIR=$(pwd)

export PYTHONPATH=${PYTHONPATH}:${CURA_APP_DIR}/Uranium:${CURA_APP_DIR}/Cura

Xvfb :1.0 -screen 0 1280x800x16 &
export DISPLAY=:1.0
export QT_QPA_PLATFORM=offscreen
python3 "${CURA_APP_DIR}"/Cura/plugins/SmartSlicePlugin/tests/run.py