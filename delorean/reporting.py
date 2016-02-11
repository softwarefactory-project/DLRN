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
import os
import shutil
from time import gmtime
from time import strftime

from six.moves.urllib import parse

from delorean.db import getCommits
from delorean.db import getSession


def get_commit_url(commit, pkg):
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
    else:
        commit_url = upstream_url
    return commit_url


def genreports(cp, packages, options):
    global session
    session = getSession('sqlite:///commits.sqlite')

    # Generate report of the last 300 package builds
    target = cp.get("DEFAULT", "target")
    src = cp.get("DEFAULT", "source")
    reponame = cp.get("DEFAULT", "reponame")

    html_struct = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>RDO Packaging By Delorean</title>
        <link rel="stylesheet" href="styles.css">
    </head>
    <body>
    <h1><i class='fa fa-chevron-circle-right pull-left'></i>%s - %s (%s)</h1>
    """ % (reponame.capitalize(),
           target.capitalize(),
           src)

    table_header = """
    <table id="delorean">
        <tr>
            <th>Build Date Time</th>
            <th>Commit Date Time</th>
            <th>Project Name</th>
            <th>Commit Hash</th>
            <th>Status</th>
            <th>Repository</th>
            <th>Build Log</th>
        </tr>
    """
    html = list()
    html.append(html_struct)
    html.append(table_header)
    commits = getCommits(session, without_status="RETRY", limit=300)

    for commit in commits:
        if commit.status == "SUCCESS":
            html.append('<tr class="success">')
        else:
            html.append('<tr>')
        dt_build = gmtime(commit.dt_build)
        dt_commit = gmtime(commit.dt_commit)
        html.append("<td>%s</td>" % strftime("%Y-%m-%d %H:%M:%S", dt_build))
        html.append("<td>%s</td>" % strftime("%Y-%m-%d %H:%M:%S", dt_commit))
        html.append("<td>%s</td>" % commit.project_name)

        for pkg in packages:
            project = pkg["name"]
            if project == commit.project_name:
                commit_url = get_commit_url(commit, pkg)
                html.append("<td class='commit'>"
                            "<i class='fa fa-git pull-left'>"
                            "</i><a href='%s%s'>%s</a></td>" %
                            (commit_url,
                             commit.commit_hash,
                             commit.commit_hash))

        if commit.status == "SUCCESS":
            html.append("<td><i class='fa fa-thumbs-o-up pull-left' "
                        "style='color:green'></i>SUCCESS</td>")
        else:
            html.append("<td><i class='fa fa-thumbs-o-down pull-left' "
                        "style='color:red'></i>FAILED</td>")
        html.append("<td><i class='fa fa-link pull-left' "
                    "style='color:#004153'></i><a href=\"%s\">repo</a></td>" %
                    commit.getshardedcommitdir())
        html.append("<td><i class='fa fa-link pull-left' "
                    "style='color:#004153'></i>"
                    "<a href='%s/rpmbuild.log'>build log</a></td>"
                    % commit.getshardedcommitdir())
        html.append("</tr>")
    html.append("</table></html>")

    stylesheets_path = os.path.dirname(os.path.abspath(__file__))
    css_file = os.path.join(stylesheets_path, 'stylesheets/styles.css')
    if not os.path.exists(os.path.join(cp.get("DEFAULT", "datadir"), "repos")):
        os.mkdir(os.path.join(cp.get("DEFAULT", "datadir"), "repos"))

    shutil.copy2(css_file, os.path.join(cp.get("DEFAULT", "datadir"),
                                        "repos", "styles.css"))

    report_file = os.path.join(cp.get("DEFAULT", "datadir"),
                               "repos", "report.html")
    with open(report_file, "w") as fp:
        fp.write("".join(html))

    if options.head_only:
        msg = " (all commit not built)"
    else:
        msg = ""

    # Generate report of status for each project
    table_header = """
    <table id="delorean">
        <tr>
            <th>Project Name</th>
            <th>Status</th>
            <th>First failure after success%s</th>
            <th>Number of days since last success</th>
        </tr>
    """ % msg
    html = list()
    html.append(html_struct)
    html.append(table_header)
    # Find the most recent successfull build
    # then report on failures since then
    for package in sorted(packages,
                          cmp=lambda x, y:
                          cmp(x['name'], y['name'])):
        name = package["name"]
        commits = getCommits(session, project=name)
        first_commit = commits.first()

        if commits.count() == 0:
            continue

        if first_commit.status == "SUCCESS":
            html.append('<tr class="success">')
            html.append("<td>%s</td>" % name)
            html.append("<td><i class='fa fa-thumbs-o-up pull-left' "
                        "style='color:green'></i>"
                        "<a href='%s/rpmbuild.log'>SUCCESS</a></td>"
                        % first_commit.getshardedcommitdir())
            html.append("<td></td>")
            html.append("<td></td>")
        else:
            html.append("<tr>")
            html.append("<td>%s</td>" % name)

            if first_commit.status == "RETRY":
                html.append("<td><i class='fa fa-warning pull-left' "
                            "style='color:yellow'></i>"
                            "<a href='%s/rpmbuild.log'>RETRY</a></td>"
                            % first_commit.getshardedcommitdir())
            else:
                html.append("<td><i class='fa fa-thumbs-o-down pull-left' "
                            "style='color:red'></i>"
                            "<a href='%s/rpmbuild.log'>FAILED</a></td>"
                            % first_commit.getshardedcommitdir())

            commits = getCommits(session, project=name, with_status="SUCCESS")
            last_success = commits.first()

            last_success_dt = 0
            if last_success is not None:
                last_success_dt = last_success.dt_build

                commits = getCommits(session, project=name,
                                     with_status="FAILED", order="asc",
                                     since=last_success_dt)
            else:
                commits = getCommits(session, project=name,
                                     with_status="FAILED", order="asc")
            if commits.count() == 0:
                html.append("<td>??????</td>")
            else:
                commit = commits.first()
                html.append("<td><i class='fa fa-git pull-left'></i>"
                            "<a href='%s%s'>%s</a>"
                            " (<a href='%s/rpmbuild.log'>build log</a>)</td>"
                            % (get_commit_url(commit, package),
                               commit.commit_hash, commit.commit_hash,
                               commit.getshardedcommitdir()))
            if last_success_dt == 0:
                html.append("<td>Never</td>")
            else:
                html.append("<td>%d days</td>" %
                            (datetime.now() -
                             datetime.fromtimestamp(last_success_dt)).days)

        html.append("</tr>")
    html.append("</table></html>")

    report_file = os.path.join(cp.get("DEFAULT", "datadir"),
                               "repos", "status_report.html")
    with open(report_file, "w") as fp:
        fp.write("\n".join(html))
