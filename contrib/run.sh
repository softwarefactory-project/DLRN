#!/bin/bash
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

if [ -n "$DLRNAPI_DBPATH" ];
then
    export CONFIG_FILE='/data/custom_config.py'
    echo "DB_PATH = \"$DLRNAPI_DBPATH\"" > /data/custom_config.py
fi

if [ -n "$DLRNAPI_USE_SAMPLE_DATA" ];
then
    python3 /import.py
    mkdir -p /data/repos/17/23/17234e9ab9dfab4cf5600f67f1d24db5064f1025_024e24f0
    mkdir -p /data/repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc_8170b868
    mkdir -p /data/repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0e77_8170b868
fi

python3 /DLRN/scripts/api.py
