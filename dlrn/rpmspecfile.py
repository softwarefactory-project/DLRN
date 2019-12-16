#
# Copyright (C) 2015-2016 Red Hat, Inc.
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
the dependencies.
'''

from __future__ import print_function
import os
import re
import sys

name_regexp = re.compile(r'^Name:\s*(.+)\s*$')
package_regexp = re.compile(r'^(Provides:|%package)\s+(-n)?\s*(.+)\s*$')
define_regexp = re.compile(r'[^#]*%(?:define|global)\s+(.+)\s+(.+)\s*$')
build_requires_regexp = re.compile(r'^(?:Build)?Requires(?:\([^\)]+\))?:'
                                   r'\s*(.+)\s*$')


class RpmSpecFile(object):
    def __init__(self, content):
        self._defines = {}
        self._packages = []
        self._build_requires = []
        self.name = '<none>'
        self._provided = {}
        for line in content.split('\n'):
            # lookup macros
            res = define_regexp.search(line)
            if res:
                self._defines[res.group(1)] = res.group(2)
            else:
                # lookup Name:
                res = name_regexp.search(line)
                if res:
                    if self.name == '<none>':
                        self.name = self._expand_defines(res.group(1))
                        self._packages.append(self.name)
                        self._defines['name'] = self.name
                else:
                    # lookup package
                    res = package_regexp.search(line)
                    if res:
                        pkg = re.split(r'\s+|[><=]',
                                       self._expand_defines(res.group(3)))[0]
                        if res.group(2) or res.group(1) == 'Provides:':
                            pkg_name = pkg
                        else:
                            pkg_name = self.name + '-' + pkg
                        self._packages.append(pkg_name)
                        self._provided[pkg_name] = self.name
                    else:
                        # lookup BuildRequires:
                        res = build_requires_regexp.search(line)
                        if res:
                            # split requires on the same lines and
                            # remove >=, <= or = clauses
                            self._build_requires.extend(
                                [re.split(r'\s+|[><=]',
                                          self._expand_defines(req))[0]
                                 for req in re.split(r'\s*,\s*',
                                                     res.group(1))])
        # remove dups
        self._build_requires = list(set(self._build_requires))

    def _expand_defines(self, content):
        lookup_start = content.find('%{')
        lookup_end = content.find('}', lookup_start)
        if (content[lookup_start:lookup_start + 2] ==
           '%{' and content[lookup_end] == '}'):
            return self._expand_defines(
                content[:lookup_start] +
                self._defines.get(content[lookup_start + 2:lookup_end], '') +
                content[lookup_end + 1:])
        return content

    def packages(self):
        return self._packages

    def build_requires(self):
        return self._build_requires

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return self.name == other.name


class RpmSpecCollection(object):
    def __init__(self, initial_list=None, debug=False):
        if initial_list:
            self.specs = initial_list
        else:
            self.specs = []
        self.debug = debug

    def compute_order(self):
        # sub-package to package associative array
        self.pkg = {}
        # list to return the computed order
        self.order = []
        # keep status of the progress by
        # package: 0 not processed, 1
        # processing dependencies, 2 already
        # processed
        self.color = {}

        for spec in sorted(self.specs):
            self.pkg[spec.name] = spec
            self.color[spec.name] = 0
            for pkg_name in spec.packages():
                self.pkg[pkg_name] = spec
        for spec in self.specs:
            if self.color[spec.name] == 0:
                self._visit(spec)
        return self.order

    def _visit(self, spec):
        if self.color[spec.name] == 1:
            sys.stderr.write('cycle detected on %s\n' %
                             ', '.join([k for k in self.color
                                        if self.color[k] == 1]))
        elif self.color[spec.name] == 2:
            return
        else:
            self.color[spec.name] = 1
            for breq in spec.build_requires():
                if breq in spec.packages():
                    continue
                if breq in self.pkg:
                    self._visit(self.pkg[breq])
        self.color[spec.name] = 2
        self.order.append(spec.name)


def _main():
    if len(sys.argv) > 2:
        # output the graph in a graphviz compliant format if -g is passed
        if sys.argv[1] == '-g':
            specs = RpmSpecCollection([RpmSpecFile(open(arg).read(-1))
                                       for arg in sys.argv[2:]],
                                      debug=os.getenv('DEBUG'))
            specnames = specs.compute_order()
            print('digraph G {')
            for spec in specs.specs:
                if spec.name not in specnames:
                    continue
                for breq in spec.build_requires():
                    if breq not in spec.packages() and breq in specs.pkg:
                        print('  "%s" -> "%s";' %
                              (spec.name, specs.pkg[breq].name))
            print('}')
        else:
            specs = RpmSpecCollection([RpmSpecFile(open(arg).read(-1))
                                       for arg in sys.argv[1:]],
                                      debug=os.getenv('DEBUG'))
            print('Build order:')
            print('\n'.join(specs.compute_order()))
    else:
        spec = RpmSpecFile(open(sys.argv[1]).read(-1))
        print('Packages:', ', '.join(spec.packages()))
        print('BuildRequires:', ', '.join(spec.build_requires()))


if __name__ == "__main__":
    _main()

# rpmspecfile.py ends here
