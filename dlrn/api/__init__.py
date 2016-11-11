from flask import Flask

app = Flask(__name__)
app.config.from_object('dlrn.api.config')

from dlrn.api import dlrn_api
