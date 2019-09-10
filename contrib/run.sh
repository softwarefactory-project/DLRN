#!/bin/bash

if [ -n "$DLRNAPI_USE_SAMPLE_DATA" ];
then
    python /import.py
    mkdir -p /data/repos/17/23/17234e9ab9dfab4cf5600f67f1d24db5064f1025_024e24f0
    mkdir -p /data/repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc_8170b868
    mkdir -p /data/repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0e77_8170b868
fi

python /DLRN/scripts/api.py
