import os

from flask import Flask

app = Flask(__name__)
app.config.from_object('dlrn.api.config')
try:
    app.config.from_pyfile(os.environ['CONFIG_FILE'], silent=True)
except KeyError:
    pass

from dlrn.api import dlrn_api  # nopep8
