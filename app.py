from flask import Flask
from flask import request
from workshop import openshift_info
from flask.json import jsonify
import signal
import os
import sys

SECRET = os.environ.get("SECRET", "verysecret")
IAM_FILE = "./iam"

app = Flask(__name__)

openshift_workshop = openshift_info.OpenShiftWorkshop()


@app.route('/health')
def health():
    return "OK"


@app.route('/')
def main():
    secret = request.args.get('secret')
    if not check_secret(secret):
        return jsonify({"status": 403, "msg": "Forbidden"}), 403

    pods = openshift_workshop.get_pods()
    me = openshift_workshop.get_self()
    routes = openshift_workshop.get_routes()

    return jsonify({"pods": pods, "me": me, "routes": routes})


@app.route('/iam')
def iam():
    if os.path.isfile(IAM_FILE):
        with open(IAM_FILE, "r") as fp:
            iam = fp.read()
            return iam
    else:
        return "Could not find the 'iam' file", 404


@app.route('/iam/<name>', methods=['POST'])
def iam_post(name):
    with open(IAM_FILE, "w") as fp:
        fp.write(name)

    return jsonify({"msg": "OK", "status": 200})


def check_secret(secret):
    return secret == SECRET


def signal_term_handler(signal, frame):
    app.logger.warn('got SIGTERM')
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_term_handler)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
