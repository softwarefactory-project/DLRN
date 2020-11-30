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

from datetime import datetime
from functools import partial
from operator import itemgetter
import os
import shutil
from time import gmtime
from time import strftime

from six.moves.urllib import parse

import jinja2

from dlrn.config import getConfigOptions
from dlrn.db import Commit
from dlrn.db import getCommits


def get_commit_url(commit, pkg):
    try:
        upstream_url = parse.urlsplit(pkg["upstream"])

        if upstream_url.netloc == "git.openstack.org":
            commit_url = ("http",
                          upstream_url.netloc,
                          "/cgit%s/commit/?id=" % upstream_url.path,
                          "", "", "")
            commit_url = parse.urlunparse(commit_url)
        elif upstream_url.netloc == "github.com":
            commit_url = ("https",
                          upstream_url.netloc,
                          "%s/commit/" % upstream_url.path,
                          "", "", "")
            commit_url = parse.urlunparse(commit_url)
        elif upstream_url.netloc == "opendev.org":
            commit_url = ("https",
                          upstream_url.netloc,
                          "%s/commit/" % upstream_url.path,
                          "", "", "")
            commit_url = parse.urlunparse(commit_url)
        else:
            # Fallback when no cgit URL can be defined
            commit_url = pkg["upstream"]
    except KeyError:
        # This should not happen, but pkg['upstream'] may not be present
        # after some error in the gitrepo driver
        commit_url = ''

    return commit_url


def _jinja2_filter_strftime(date, fmt="%Y-%m-%d %H:%M:%S"):
    gmdate = gmtime(date)
    return "%s" % strftime(fmt, gmdate)


def _jinja2_filter_get_commit_url(commit, packages):
    for pkg in packages:
        project = pkg["name"]
        if project == commit.project_name:
            return get_commit_url(commit, pkg)
    return "???"


def genreports(packages, head_only, session, all_commits):
    config_options = getConfigOptions()

    # Generate report of the last 300 package builds
    target = config_options.target
    src = config_options.source
    reponame = config_options.reponame
    templatedir = config_options.templatedir
    project_name = config_options.project_name
    datadir = config_options.datadir
    repodir = os.path.join(datadir, "repos")

    css_file = os.path.join(templatedir, 'stylesheets/styles.css')

    # create directories
    if not os.path.exists(repodir):
        os.makedirs(repodir)

    # configure jinja and filters
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([templatedir]))
    jinja_env.filters["strftime"] = _jinja2_filter_strftime
    jinja_env.filters["get_commit_url"] = \
        partial(_jinja2_filter_get_commit_url, packages=packages)

    # generate build report
    commits = getCommits(session, without_status="RETRY", limit=300)
    jinja_template = jinja_env.get_template("report.j2")
    content = jinja_template.render(reponame=reponame,
                                    src=src,
                                    project_name=project_name,
                                    target=target,
                                    commits=commits)
    shutil.copy2(css_file, os.path.join(repodir, "styles.css"))
    report_file = os.path.join(repodir, "report.html")
    with open(report_file, "w") as fp:
        fp.write(content)

    # Generate status report
    if head_only:
        msg = "(all commit not built)"
    else:
        msg = ""

    pkgs = []
    # Find the most recent successfull build
    # then report on failures since then
    for package in packages:
        name = package["name"]
        commits = getCommits(session, project=name, limit=1)

        # No builds
        if commits.count() == 0:
            continue

        pkgs.append(package)
        last_build = commits.first()
        package["last_build"] = last_build

        # last build was successul
        if last_build.status == "SUCCESS":
            continue

        # Retrieve last successful build
        commits = getCommits(session, project=name, with_status="SUCCESS",
                             limit=1)

        # No successful builds
        if commits.count() == 0:
            commits = getCommits(session, project=name, with_status="FAILED",
                                 order="asc")
            package["first_failure"] = commits.first()
            package["days"] = -1
            continue

        last_success = commits.first()
        last_success_dt = last_success.dt_build

        commits = getCommits(session, project=name, with_status="FAILED",
                             order="asc", limit=None)
        commits = commits.filter(Commit.dt_build > last_success_dt)
        package["first_failure"] = commits.first()
        package["days"] = (datetime.now() -
                           datetime.fromtimestamp(last_success_dt)).days

    pkgs = sorted(pkgs, key=itemgetter("name"))
    jinja_template = jinja_env.get_template("status_report.j2")
    content = jinja_template.render(msg=msg,
                                    reponame=reponame,
                                    src=src,
                                    project_name=project_name,
                                    target=target,
                                    pkgs=pkgs)

    report_file = os.path.join(repodir, "status_report.html")
    with open(report_file, "w") as fp:
        fp.write(content)

    jinja_template = jinja_env.get_template("status_report_csv.j2")
    content = jinja_template.render(msg=msg,
                                    reponame=reponame,
                                    src=src,
                                    project_name=project_name,
                                    target=target,
                                    pkgs=pkgs)

    report_file = os.path.join(repodir, "status_report.csv")
    with open(report_file, "w") as fp:
        fp.write(content)

    # Create a report for the pending packages
    jinja_template = jinja_env.get_template("queue.j2")
    pending_commits = []
    for commit in all_commits:
        old_commit = getCommits(session, project=commit.project_name,
                                without_status="RETRY", limit=None).filter(
            Commit.commit_hash == commit.commit_hash).filter(
            Commit.distro_hash == commit.distro_hash).filter(
            Commit.extended_hash == commit.extended_hash).first()
        if not old_commit:
            pending_commits.append(commit)

    content = jinja_template.render(reponame=reponame,
                                    src=src,
                                    target=target,
                                    commits=pending_commits)
    report_file = os.path.join(repodir, "queue.html")
    with open(report_file, "w") as fp:
        fp.write(content)
