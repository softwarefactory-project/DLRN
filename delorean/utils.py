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
import sys
import yaml

import sqlalchemy

from delorean.db import Commit
from delorean.db import getSession


# Load a yaml file into a db session, used to populate a in memory database
# during tests
def loadYAML(session, yamlfile):
    fp = open(yamlfile)
    data = yaml.load(fp)
    fp.close()

    for commit in data['commits']:
        c = Commit(**commit)
        session.add(c)
    session.commit()


# Save a database to yaml, this is a helper function to assist in creating
# yaml files for unit tests.
def saveYAML(session, yamlfile):
    data = {}

    attrs = []
    for a in dir(Commit):
        if type(getattr(Commit, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['commits'] = []
    for commit in session.query(Commit).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(commit, a))
        data['commits'].append(d)
    fp = open(yamlfile, "w")
    fp.write(yaml.dump(data, default_flow_style=False))
    fp.close()


if __name__ == '__main__':
    s = getSession('sqlite:///%s' % sys.argv[1])
    saveYAML(s, sys.argv[1] + ".yaml")
    s = getSession('sqlite://')
    loadYAML(s, sys.argv[1] + ".yaml")
    print(s.query(Commit).first().project_name)
