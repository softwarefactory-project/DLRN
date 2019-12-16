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

import unittest

from dlrn.rpmspecfile import RpmSpecCollection
from dlrn.rpmspecfile import RpmSpecFile


class TestRpmSpecFile(unittest.TestCase):

    def test_basic_package(self):
        spec = RpmSpecFile(BASIC_SPEC_CONTENT)
        self.assertEqual(spec.packages(), ['package'])

    def test_package_with_macro(self):
        spec = RpmSpecFile(MACRO_SPEC_CONTENT)
        self.assertEqual(spec.packages(), ['package'])

    def test_package_with_provides(self):
        spec = RpmSpecFile(PROVIDES_SPEC_CONTENT)
        self.assertEqual(spec.packages(), ['package', 'oldname'])

    def test_sub_package(self):
        spec = RpmSpecFile(SUB_PKG_CONTENT)
        self.assertEqual(spec.packages(), ['package', 'package-subpkg-toto'])

    def test_nsub_package(self):
        spec = RpmSpecFile(NSUB_PKG_CONTENT)
        self.assertEqual(spec.packages(), ['package', 'pre-serv-post'])

    def test_name_package(self):
        spec = RpmSpecFile(NAME_PKG_CONTENT)
        self.assertEqual(spec.packages(), ['package', 'package-package-toto'])

    def test_build_requires(self):
        spec = RpmSpecFile(DEP_SPEC_CONTENT)
        self.assertEqual(set(spec.build_requires()), set(['dep1', 'dep2']))

    def test_build_requires_with_operator(self):
        spec = RpmSpecFile(OPERATOR_DEP_SPEC_CONTENT)
        self.assertEqual(set(spec.build_requires()), set(['dep1', 'dep2']))

    def test_build_requires_with_operator_no_space(self):
        spec = RpmSpecFile(OPERATOR_DEP_SPEC_CONTENT2)
        self.assertEqual(set(spec.build_requires()), set(['dep1', 'dep2']))


class TestRpmSpecCollection(unittest.TestCase):

    def test_basic(self):
        specs = RpmSpecCollection([RpmSpecFile(BASIC_SPEC_CONTENT)])
        self.assertEqual(specs.compute_order(), ['package'])

    def test_multiple_names(self):
        specs = RpmSpecCollection([RpmSpecFile(MULTIPLE_NAME_CONTENT)])
        self.assertEqual(specs.compute_order(), ['package'])

    def test_dep(self):
        specs = RpmSpecCollection([RpmSpecFile(BASIC_SPEC_CONTENT),
                                   RpmSpecFile(BASIC2_SPEC_CONTENT)])
        self.assertEqual(specs.compute_order(), ['package', 'packageC'])

    def test_dep2(self):
        specs = RpmSpecCollection([RpmSpecFile(BASIC_SPEC_CONTENT),
                                  RpmSpecFile(BASIC2_SPEC_CONTENT),
                                   RpmSpecFile(BASIC3_SPEC_CONTENT)])
        self.assertEqual(specs.compute_order(), ['package',
                                                 'packageC',
                                                 'packageB'])

    def test_dep_sub(self):
        specs = RpmSpecCollection([RpmSpecFile(DEP_SUB_PKG_CONTENT),
                                  RpmSpecFile(SUB_PKG_CONTENT)])
        self.assertEqual(specs.compute_order(), ['package',
                                                 'packageD'])


BASIC_SPEC_CONTENT = '''
Name: package
'''

BASIC2_SPEC_CONTENT = '''
Name: packageC
Requires(pre): package
'''

BASIC3_SPEC_CONTENT = '''
Name: packageB
BuildRequires: packageC, unknown
'''

MACRO_SPEC_CONTENT = '''
%define name package

Name: %{name}
'''

PROVIDES_SPEC_CONTENT = '''
Name: package
Provides: oldname = 1.0
'''

DEP_SPEC_CONTENT = '''
Name: package
BuildRequires: dep1, dep2
'''

OPERATOR_DEP_SPEC_CONTENT = '''
Name: package
BuildRequires: dep1, dep2 >= 0.1
'''

OPERATOR_DEP_SPEC_CONTENT2 = '''
Name: package
BuildRequires: dep1, dep2>=0.1
'''

SUB_PKG_CONTENT = '''
Name: package
%define serv subpkg
%package %{serv}-toto
'''

NSUB_PKG_CONTENT = '''
Name: package
%global sub serv
%global serv %{sub}
%package -n pre-%{serv}-post
'''

SUB_PKG_CONTENT = '''
Name: package
%define serv subpkg
%package %{serv}-toto
'''

NAME_PKG_CONTENT = '''
Name: package
%package %{name}-toto
'''

DEP_SUB_PKG_CONTENT = '''
Name: packageD
BuildRequires: package-subpkg-toto
'''

MULTIPLE_NAME_CONTENT = '''
Name: package

%prep
cat > fake.egg-info <<EOF
Name: anothername
EOF
'''

if __name__ == "__main__":
    unittest.main()

# test_rpmspecfile.py ends here
