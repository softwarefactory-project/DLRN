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

import dlrn.shell
import filecmp
import logging
import multiprocessing
import os
import sh
import shutil

from six.moves.urllib.request import urlopen

from dlrn.config import getConfigOptions
from dlrn.utils import import_object
from time import time

logger = logging.getLogger("dlrn-build")


def _get_yumrepodir(commit):
    return os.path.join("repos", commit.getshardedcommitdir())


def build_worker(packages, commit, run_cmd=False, build_env=None,
                 dev_mode=False, use_public=False, order=False,
                 sequential=False):

    if run_cmd:
        try:
            run(run_cmd, commit, build_env, dev_mode, use_public, order,
                do_build=False)
            return [commit, '', '', None]
        except Exception as e:
            return [commit, '', '', e]

    logger.info("Processing %s %s" % (commit.project_name, commit.commit_hash))

    notes = ""
    try:
        built_rpms, notes = build(packages, commit, build_env, dev_mode,
                                  use_public, order, sequential)
        return [commit, built_rpms, notes, None]
    except Exception as e:
        return [commit, '', '', e]


def get_version_from(packages, project_name):
    for package in packages:
        if package['name'] == project_name:
            return package.get('version-from')
    return None


def build(packages, commit, env_vars, dev_mode, use_public,
          bootstrap, sequential):
    if commit.type == "rpm":
        return build_rpm(
            packages, commit, env_vars, dev_mode, use_public,
            bootstrap, sequential)
    elif commit.type == "container":
        return build_container(
            packages, commit, env_vars, dev_mode, use_public,
            bootstrap, sequential)
    else:
        raise Exception("Unknown type %s" % commit.type)


def build_container(packages, commit, env_vars, dev_mode, use_public,
                    bootstrap, sequential):
    raise NotImplemented()


def build_rpm(packages, commit, env_vars, dev_mode, use_public,
              bootstrap, sequential):
    config_options = getConfigOptions()
    # Set the build timestamp to now
    commit.dt_build = int(time())

    project_name = commit.project_name
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = _get_yumrepodir(commit)
    version_from = get_version_from(packages, project_name)

    try:
        build_rpm_wrapper(commit, dev_mode, use_public, bootstrap,
                          env_vars, sequential,
                          version_from=version_from)
    except Exception as e:
        logger.error('Build failed. See logs at: %s/%s/' % (datadir,
                                                            yumrepodir))
        raise Exception("Error in build_rpm_wrapper for %s: %s" %
                        (project_name, e))

    # This *could* have changed during the build, see kojidriver.py
    yumrepodir = _get_yumrepodir(commit)
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    built_rpms = []
    for rpm in os.listdir(yumrepodir_abs):
        if rpm.endswith(".rpm"):
            built_rpms.append(os.path.join(yumrepodir, rpm))
    if not built_rpms:
        raise Exception("No rpms built for %s" % project_name)

    notes = "OK"

    if not os.path.isfile(os.path.join(yumrepodir_abs, "installed")):
        logger.error('Build failed. See logs at: %s/%s/' % (datadir,
                                                            yumrepodir))
        raise Exception("Error installing %s" % project_name)
    else:
        # Overwrite installed file, adding the repo reference
        with open(os.path.join(yumrepodir_abs, "installed"), "w") as fp:
            fp.write("%s %s %s" % (commit.project_name,
                                   commit.commit_hash,
                                   commit.distro_hash))
    return built_rpms, notes


def build_rpm_wrapper(commit, dev_mode, use_public, bootstrap, env_vars,
                      sequential, version_from=None):
    config_options = getConfigOptions()
    # Get the worker id
    if sequential is True:
        worker_id = 1
    else:
        worker_id = multiprocessing.current_process()._identity[0]

    # Retrieve build driver
    build_driver = config_options.build_driver
    buildrpm = import_object(build_driver, cfg_options=config_options)

    # FIXME(hguemar): move all the mock config logic to driver
    mock_config = "dlrn-" + str(worker_id) + ".cfg"
    scriptsdir = os.path.realpath(config_options.scriptsdir)
    configdir = os.path.realpath(config_options.configdir)
    datadir = os.path.realpath(config_options.datadir)
    baseurl = config_options.baseurl
    templatecfg = os.path.join(configdir, config_options.target + ".cfg")
    newcfg = os.path.join(datadir, mock_config + ".new")
    oldcfg = os.path.join(datadir, mock_config)
    shutil.copyfile(templatecfg, newcfg)

    if (config_options.build_driver ==
            'dlrn.drivers.kojidriver.KojiBuildDriver' and
            config_options.fetch_mock_config):
        buildrpm.write_mock_config(oldcfg)

    # Add the most current repo, we may have dependencies in it
    if os.path.exists(os.path.join(datadir, "repos", "current", "repodata")):
        # Get the real path for the current repo, this could change during
        # parallel builds
        repolink = os.readlink(os.path.join(datadir, "repos", "current"))
        if repolink.startswith('/'):
            # absolute symlink
            repopath = repolink
        else:
            # relative symlink
            repopath = os.path.join(datadir, "repos", repolink)
        with open(newcfg, "r") as fp:
            contents = fp.readlines()
        # delete the last line which must be """
        contents = contents[:-1]
        contents = contents + ["[local]\n", "name=local\n",
                               "baseurl=file://%s\n" % repopath,
                               "enabled=1\n", "gpgcheck=0\n", "priority=1\n",
                               "\"\"\""]
        with open(newcfg, "w") as fp:
            fp.writelines(contents)

    # Set the worker id in the mock configuration, to allow multiple workers
    # for the same config
    with open(newcfg, "r") as fp:
        contents = fp.readlines()
    with open(newcfg, "w") as fp:
        for line in contents:
            if line.startswith("config_opts['root']"):
                line = line[:-2] + "-" + str(worker_id) + "'\n"
            fp.write(line)

    # delete the last line which must be """
    with open(newcfg, "r") as fp:
        contents = fp.readlines()
    contents = contents[:-1]

    try:
        if not baseurl:
            raise Exception("No baseurl defined")
        r = urlopen(baseurl + "/delorean-deps.repo")
        delorean_deps = True
    except Exception as e:
        logger.warning(
            "Could not open %s/delorean-deps.repo. If some dependent"
            " repositories must be included in the mock then check the"
            " baseurl value in projects.ini, and make sure the file can be"
            " downloaded." % baseurl)
        delorean_deps = False

    if delorean_deps:
        contents.extend(map(lambda x: x.decode('utf8'), r.readlines()))
        contents = contents + ["\n\"\"\""]
        with open(newcfg, "w") as fp:
            fp.writelines(contents)

    if dev_mode or use_public:
        with open(newcfg, "r") as fp:
            contents = fp.readlines()

        # delete the last line which must be """
        contents = contents[:-1]
        try:
            r = urlopen(baseurl + "/current/delorean.repo")
        except Exception as e:
            logger.error("Could not open %s/current/delorean.repo. Check the "
                         "baseurl value in projects.ini, and make sure the "
                         "file can be downloaded." % baseurl)
            raise e

        contents.extend(map(lambda x: x.decode('utf8'), r.readlines()))
        contents.extend(["\n\"\"\""])

        with open(newcfg, "w") as fp:
            fp.writelines(contents)

    # don't change dlrn.cfg if the content hasn't changed to prevent
    # mock from rebuilding its cache.
    try:
        if not filecmp.cmp(newcfg, oldcfg):
            if (config_options.build_driver ==
                    'dlrn.drivers.kojidriver.KojiBuildDriver'):
                if not config_options.fetch_mock_config:
                    shutil.copyfile(newcfg, oldcfg)
            else:
                shutil.copyfile(newcfg, oldcfg)
    except OSError:
        shutil.copyfile(newcfg, oldcfg)

    # Set env variable for Copr configuration
    if (config_options.build_driver ==
            'dlrn.drivers.coprdriver.CoprBuildDriver' and
            config_options.coprid):
        os.environ['COPR_ID'] = config_options.coprid

    # Set release numbering option
    if config_options.release_numbering == '0.1.date.hash':
        os.environ['RELEASE_NUMBERING'] = '0.1.date.hash'
    else:
        os.environ['RELEASE_NUMBERING'] = '0.date.hash'

    # Set env variable for mock configuration
    os.environ['MOCK_CONFIG'] = mock_config

    # if bootstraping, set the appropriate mock config option
    if bootstrap is True:
        additional_mock_options = '-D repo_bootstrap 1'
    else:
        additional_mock_options = None

    dlrn.shell.pkginfo.preprocess(package_name=commit.project_name,
                                  commit_hash=commit.commit_hash)

    if (config_options.pkginfo_driver ==
            'dlrn.drivers.gitrepo.GitRepoDriver' and
            config_options.keep_tarball):
        if commit.commit_branch == config_options.source:
            # We are following the master tarball here, use it
            os.environ['DLRN_KEEP_TARBALL'] = '1'
        else:
            if 'DLRN_KEEP_TARBALL' in os.environ:
                del os.environ['DLRN_KEEP_TARBALL']

    if config_options.keep_changelog:
        os.environ['DLRN_KEEP_CHANGELOG'] = '1'

    if (config_options.pkginfo_driver == 'dlrn.drivers.local.LocalDriver'):
        os.environ['DLRN_KEEP_SPEC_AS_IS'] = '1'

    # We may do some git repo manipulation, so we need to make sure the
    # right commit is there
    os.environ['DLRN_SOURCE_COMMIT'] = commit.commit_hash

    run(os.path.join(scriptsdir, "build_srpm.sh"), commit, env_vars,
        dev_mode, use_public, bootstrap, version_from=version_from)

    # SRPM is built, now build the RPM using the driver
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = _get_yumrepodir(commit)
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    # If we are using the downstream driver, write the reference commit
    if (config_options.pkginfo_driver ==
            'dlrn.drivers.downstream.DownstreamInfoDriver'):
        dlrn.shell.pkginfo._write_reference_commit(yumrepodir_abs)

    buildrpm.build_package(output_directory=yumrepodir_abs,
                           additional_mock_opts=additional_mock_options,
                           package_name=commit.project_name,
                           commit=commit)


def run(program, commit, env_vars, dev_mode, use_public, bootstrap,
        do_build=True, version_from=None):
    config_options = getConfigOptions()
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = _get_yumrepodir(commit)
    yumrepodir_abs = os.path.join(datadir, yumrepodir)
    project_name = commit.project_name
    repo_dir = commit.repo_dir

    if do_build:
        # If yum repo already exists remove it and assume we're starting fresh
        if os.path.exists(yumrepodir_abs):
            shutil.rmtree(yumrepodir_abs)
        os.makedirs(yumrepodir_abs)

    if version_from:
        logger.info('Taking tags to define version from %s' % version_from)
        git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
        git.merge('-s', 'ours', '-m', '"fake merge tags"', version_from)

    run_cmd = []
    if env_vars:
        for env_var in env_vars:
            run_cmd.append(env_var)

    run_cmd.extend([program,
                    config_options.target, project_name,
                    os.path.join(datadir, yumrepodir),
                    datadir, config_options.baseurl,
                    os.path.realpath(commit.distgit_dir)])
    if not do_build:
        logger.info('Running %s' % ' '.join(run_cmd))

    try:
        sh.env(run_cmd, _err=process_mock_output, _out=process_mock_output)
    except Exception as e:
        # This *could* have changed during the build, see kojidriver.py
        datadir = os.path.realpath(config_options.datadir)
        yumrepodir = _get_yumrepodir(commit)
        logger.error('cmd failed. See logs at: %s/%s/' % (datadir,
                                                          yumrepodir))
        raise e


def process_mock_output(line):
    if dlrn.shell.verbose_build:
        logger.info(line[:-1])
