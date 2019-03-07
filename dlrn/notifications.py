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

import copy
import jinja2
import logging
import os
import sh
import smtplib

from dlrn.config import getConfigOptions
from dlrn.reporting import get_commit_url
from email.mime.text import MIMEText

logger = logging.getLogger("dlrn-notifications")


def submit_review(commit, packages, env_vars):
    config_options = getConfigOptions()
    datadir = os.path.realpath(config_options.datadir)
    scriptsdir = os.path.realpath(config_options.scriptsdir)
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())

    project_name = commit.project_name

    for pkg in packages:
        if project_name == pkg['name']:
            break
    else:
        logger.error('Unable to find info for project'
                     ' %s' % project)
        return

    url = (get_commit_url(commit, pkg) + commit.commit_hash)
    env_vars.append('GERRIT_URL=%s' % url)
    env_vars.append('GERRIT_LOG=%s/%s' % (config_options.baseurl,
                                          commit.getshardedcommitdir()))
    maintainers = ','.join(pkg['maintainers'])
    env_vars.append('GERRIT_MAINTAINERS=%s' % maintainers)
    env_vars.append('GERRIT_TOPIC=%s' % config_options.gerrit_topic)
    logger.info('Creating a gerrit review using '
                'GERRIT_URL=%s '
                'GERRIT_MAINTAINERS=%s ' %
                (url, maintainers))

    run_cmd = []
    if env_vars:
        for env_var in env_vars:
            run_cmd.append(env_var)

    run_cmd.extend([os.path.join(scriptsdir, "submit_review.sh"),
                    project_name, os.path.join(datadir, yumrepodir),
                    datadir, config_options.baseurl,
                    os.path.realpath(commit.distgit_dir)])
    sh.env(run_cmd, _timeout=300)


def sendnotifymail(packages, commit):
    config_options = getConfigOptions()

    details = copy.copy(
        [package for package in packages
            if package["name"] == commit.project_name][0])

    email_to = details['maintainers']
    if not config_options.smtpserver:
        logger.info("Skipping notify email to %r" % email_to)
        return

    details["logurl"] = "%s/%s" % (config_options.baseurl,
                                   commit.getshardedcommitdir())
    # Render the notification template
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([config_options.templatedir]))
    jinja_template = jinja_env.get_template("notification_email.j2")
    error_body = jinja_template.render(details=details)

    msg = MIMEText(error_body)
    msg['Subject'] = '[dlrn] %s master package build failed' % \
                     commit.project_name

    email_from = 'no-reply@delorean.com'
    msg['From'] = email_from
    msg['To'] = "packagers"

    logger.info("Sending notify email to %r" % email_to)
    try:
        s = smtplib.SMTP(config_options.smtpserver)
        s.sendmail(email_from, email_to, msg.as_string())
        s.quit()
    except smtplib.SMTPException as e:
        logger.error("An issue occured when sending"
                     "notify email to %r (%s)" % (email_to, e))
    finally:
        s.close()
