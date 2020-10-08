#!/usr/bin/env bash

# UNCOMMENT FOR A SPECIFIC BRANCH OF PYWIM/PY3MF
#git clone https://github.com/tetonsim/pywim.git
#git clone https://github.com/tetonsim/py3mf.git
#mv pywim/pywim /srv/cura/Cura/plugins/SmartSlicePlugin/3rd-party/cpython-common
#mv py3mf/threemf /srv/cura/Cura/plugins/SmartSlicePlugin/3rd-party/cpython-common

CURA_APP_DIR=$(pwd)

git clone -b ${1} --depth 1 https://github.com/Ultimaker/Uranium
git clone -b ${1} --depth 1 https://github.com/Ultimaker/Cura
git clone -b ${1} --depth 1 https://github.com/Ultimaker/dm_materials materials

mv ${CURA_APP_DIR}/materials ${CURA_APP_DIR}/Cura/resources/materials


mv SmartSlicePlugin ${CURA_APP_DIR}/Cura/plugins

apt-get install -y mesa-utils xvfb
python3 -m pip install teton-3mf teton-pywim PyQt5==5.10