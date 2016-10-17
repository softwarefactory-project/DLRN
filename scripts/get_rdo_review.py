#!/usr/bin/env python
#
# Copyright (C) 2016 Red Hat, Inc.
#
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

'''
'''

from __future__ import print_function
import json
import requests
import sys

if len(sys.argv) != 3:
    sys.stderr.write('Usage: %s <Project> '
                     '<Upstream Change id>\n' % sys.argv[0])
    sys.exit(1)

r = requests.get('http://review.rdoproject.org/r'
                 "/changes/?q=status:open+project:%s&o=CURRENT_COMMIT&"
                 "o=CURRENT_REVISION" % sys.argv[1])

changes = json.loads('\n'.join(r.text.split('\n')[1:]))

for change in changes:
    for rev in change['revisions'].keys():
        lines = change['revisions'][rev]['commit']['message'].split('\n')
        for line in lines:
            parts = line.strip().split(': ')
            if (len(parts) == 2 and parts[0] == 'Upstream-Id' and
               parts[1] == sys.argv[2]):
                print(change['change_id'])
                sys.exit(0)
sys.exit(1)

# get_rdo_review.py ends here
