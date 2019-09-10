from dlrn.db import getSession
from dlrn.utils import loadYAML
from dlrn.utils import saveYAML

session = getSession('sqlite:////commits.sqlite')
loadYAML(session, '/DLRN/dlrn/tests/samples/commits_2.yaml')
session.close()
