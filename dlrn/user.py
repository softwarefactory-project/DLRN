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

import argparse
from getpass import getpass
import logging
from passlib.hash import sha512_crypt
from six.moves import configparser
from six.moves import input
import sys

from dlrn.config import ConfigOptions
from dlrn.config import setup_logging
from dlrn.db import closeSession
from dlrn.db import getSession
from dlrn.db import User


def create_user(options, db_connection):
    log = logging.getLogger(__name__)
    try:
        session = getSession(db_connection)
        olduser = session.query(User).filter(
            User.username == options.username).first()

        if olduser is None:
            if options.password is None:
                newpass = getpass("Enter password for %s: " %
                                  options.username)
            else:
                newpass = options.password

            password = sha512_crypt.hash(newpass)
            newuser = User(username=options.username,
                           password=password)
            session.add(newuser)
            session.commit()
            closeSession(session)
            log.info("User %s successfully created" % options.username)
        else:
            log.error("User %s already exists" % options.username)
            return -1
    except Exception as e:
        log.error("Failed to create user %s, %s" % (options.username, e))
        return -1
    return 0


def delete_user(options, db_connection):
    log = logging.getLogger(__name__)
    session = getSession(db_connection)
    user = session.query(User).filter(
        User.username == options.username).first()

    if user is None:
        log.error("ERROR: User %s does not exist" % options.username)
        return -1
    else:
        if not options.force:
            print("Are you sure you want to delete user %s? "
                  "If so, type YES to continue." % options.username)
            confirm = input()
            if confirm != "YES":
                print("Action not confirmed, exiting")
                return -1
        session.delete(user)
        session.commit()
        log.info("User %s deleted" % options.username)
    closeSession(session)
    return 0


def update_user(options, db_connection):
    log = logging.getLogger(__name__)
    session = getSession(db_connection)
    password = sha512_crypt.hash(options.password)
    user = session.query(User).filter(
        User.username == options.username).first()

    if user is None:
        log.error("ERROR: User %s does not exist" % options.username)
        return -1
    else:
        user.password = password
        session.add(user)
        session.commit()
        log.info("User %s updated" % options.username)
    closeSession(session)
    return 0


command_funcs = {
    'create': create_user,
    'delete': delete_user,
    'update': update_user,
}


def user_manager():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        default='projects.ini',
                        help="Config file. Default: projects.ini")
    parser.add_argument('--debug', action='store_true',
                        help="Print debug logs")

    subparsers = parser.add_subparsers(dest='command',
                                       title='subcommands',
                                       description='available subcommands')
    subparsers.required = True

    # Subcommand create
    parser_create = subparsers.add_parser('create',
                                          help='Create a user')
    parser_create.add_argument('--username', type=str, required=True,
                               help='User name')
    parser_create.add_argument('--password', type=str, help='Password')

    # Subcommand delete
    parser_delete = subparsers.add_parser('delete',
                                          help='Delete a user')
    parser_delete.add_argument('--username', type=str, required=True,
                               help='User name')
    parser_delete.add_argument('--force', dest='force',
                               action='store_true',
                               help='Do not request a confirmation')

    # Subcommand update
    parser_update = subparsers.add_parser('update',
                                          help='Update a user')
    parser_update.add_argument('--username', type=str, required=True,
                               help='User name')
    parser_update.add_argument('--password', type=str, required=True,
                               help='New password')

    options = parser.parse_args(sys.argv[1:])

    setup_logging(options.debug)

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)
    config_options = ConfigOptions(cp)

    return command_funcs[options.command](options,
                                          config_options.database_connection)
