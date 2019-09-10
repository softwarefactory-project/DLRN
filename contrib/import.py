from dlrn.db import getSession
from dlrn.utils import loadYAML

session = getSession('sqlite:////commits.sqlite')
loadYAML(session, '/DLRN/dlrn/tests/samples/commits_2.yaml')
session.close()
