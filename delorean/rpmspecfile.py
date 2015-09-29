#
# Copyright (C) 2015 Red Hat, Inc.
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

'''Basic rpm spec file parsing to be able to get the package names and
the build dependencies.
'''

from __future__ import print_function
import operator
import os
import re
import sys

name_regexp = re.compile('^Name:\s*(.+)\s*$')
package_regexp = re.compile('^%package\s+(-n)?\s*(.+)\s*$')
define_regexp = re.compile('^%(?:define|global)\s+(.+)\s+(.+)\s*$')
build_requires_regexp = re.compile('^BuildRequires:\s*(.+)\s*$')


class RpmSpecFile(object):
    def __init__(self, content):
        self._defines = {}
        self._packages = []
        self._build_requires = []
        self._name = '<none>'
        for line in content.split('\n'):
            # lookup macros
            res = define_regexp.search(line)
            if res:
                self._defines[res.group(1)] = res.group(2)
            else:
                # lookup Name:
                res = name_regexp.search(line)
                if res:
                    self._name = self._expand_defines(res.group(1))
                    self._packages.append(self._name)
                    self._defines['name'] = self._name
                else:
                    # lookup package
                    res = package_regexp.search(line)
                    if res:
                        pkg = self._expand_defines(res.group(2))
                        if res.group(1):
                            self._packages.append(pkg)
                        else:
                            self._packages.append(self._name + '-' + pkg)
                    else:
                        # lookup BuildRequires:
                        res = build_requires_regexp.search(line)
                        if res:
                            # split requires on the same lines and
                            # remove >=, <= or = clauses
                            self._build_requires.extend(
                                [re.split('\s+|[><=]', req)[0]
                                 for req in re.split('\s*,\s*',
                                                     res.group(1))])

    def _expand_defines(self, content):
        lookup_start = content.find('%{')
        lookup_end = content.find('}')
        if (content[lookup_start:lookup_start + 2] ==
           '%{' and content[lookup_end] == '}'):
            return content[:lookup_start] + \
                self._defines[content[lookup_start + 2:lookup_end]] + \
                content[lookup_end + 1:]
        return content

    def packages(self):
        return self._packages

    def build_requires(self):
        return self._build_requires


class RpmSpecCollection(object):
    def __init__(self, initial_list=None, debug=False):
        if initial_list:
            self.specs = initial_list
        else:
            self.specs = []
        self.debug = debug
        self.scores = {}

    def add_rpm_spec(self, spec):
        self.specs.append(spec)

    def compute_order(self):
        names = []
        for spec in self.specs:
            self.increase_score(spec)
            names.append(spec._name)
        ret = self.scores.items()
        if self.debug:
            sys.stderr.write(str(ret) + '\n')
        return [elt[0] for elt in sorted(ret,
                                         key=operator.itemgetter(1),
                                         reverse=True)
                if elt[0] in names]

    def increase_score(self, spec):
        if spec:
            if spec._name not in self.scores:
                self.scores[spec._name] = 0
            for breq in spec.build_requires():
                try:
                    self.scores[breq] += 1
                except KeyError:
                    self.scores[breq] = 1
                self.increase_score(self._lookup_spec(breq))

    def _lookup_spec(self, pkg_name):
        for spec in self.specs:
            if pkg_name in spec.packages():
                return spec
        return None


def _main():
    if len(sys.argv) > 2:
        specs = RpmSpecCollection([RpmSpecFile(open(arg).read(-1))
                                   for arg in sys.argv[1:]],
                                  debug=os.getenv('DEBUG'))
        print('Build order:')
        print(' '.join(specs.compute_order()))
    else:
        spec = RpmSpecFile(open(sys.argv[1]).read(-1))
        print('Packages:', ', '.join(spec.packages()))
        print('BuildRequires:', ', '.join(spec.build_requires()))


if __name__ == "__main__":
    _main()

# rpmspecfile.py ends here
