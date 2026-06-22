import os, sys

# Locate the sibling helper (service_token.py) so the import works in BOTH contexts:
#  - run as a script / %run  -> use this file's own folder (__file__ is set)
#  - copy/paste in a console  -> no __file__, so find the repo root (the folder
#    containing .git) from the cwd and point at request-example/external-app.
if "__file__" in globals():
    _HELPERS = os.path.dirname(os.path.abspath(__file__))
else:
    _root = os.getcwd()
    while _root != os.path.dirname(_root) and not os.path.isdir(
        os.path.join(_root, ".git")
    ):
        _root = os.path.dirname(_root)
    _HELPERS = os.path.join(_root, "request-example", "external-app")
sys.path.insert(0, _HELPERS)

import requests
from service_token import (
    get_service_token,
)  # client_credentials token (see service_token.py)

resp = requests.post(
    "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
    # or this URL if you want to test with your local development:
    # "http://localhost:8000/api/v1/agents/run",
    headers={"Authorization": f"Bearer {get_service_token()}"},
    json={
        "agent_name": "hscode_manager",
        "input_data": {"lead_document_title": "26014632221711"},
        "mode": "background",
    },
    verify=False,
)

print(f"Status: {resp.status_code}")
r = resp.json()
import json

with open("tmp.json", "w") as f:
    f.write(json.dumps(r, ensure_ascii=False, indent=2))

print("./tmp.json")
