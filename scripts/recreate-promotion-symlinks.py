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

# This utility script will recreate all promotion symlinks from the database,
# using the latest promotion for each.

import argparse
import os
import sys

from dlrn.db import Commit
from dlrn.db import getSession
from dlrn.db import Promotion
from six.moves import configparser
from sqlalchemy import desc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file',
                        help="Config file (required)", required=True)
    parser.add_argument('--noop',
                        help="Preview actions but do not execute them",
                        action="store_true")

    options = parser.parse_args(sys.argv[1:])

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)
    datadir = os.path.realpath(cp.get('DEFAULT', 'datadir'))
    session = getSession(cp.get('DEFAULT', 'database_connection'))

    # We need to find promotions, and for each promotion name create the
    # corresponding symlink
    promotions = session.query(Promotion.promotion_name).distinct()

    promotion_list = []
    for promotion in promotions:
        promotion_list.append(promotion.promotion_name)

    # Find latest promotions for each promotion name, and re-do the symlinks
    for name in promotion_list:
        promotion = session.query(Promotion).\
            order_by(desc(Promotion.timestamp)).\
            filter(Promotion.promotion_name == name).first()

        commit = session.query(Commit).\
            filter(Commit.id == promotion.commit_id).first()

        repo_dir = os.path.join(datadir, "repos", commit.getshardedcommitdir())
        symlink_path = os.path.join(datadir, "repos", name)
        print("Going to symlink %s to %s" % (symlink_path, repo_dir))

        if not options.noop:
            try:
                os.symlink(os.path.relpath(repo_dir,
                                           os.path.join(datadir, "repos")),
                           symlink_path + "_")
                os.rename(symlink_path + "_", symlink_path)
            except Exception as e:
                print("Symlink creation failed: %s", e)


if __name__ == '__main__':
    main()
    exit(0)
