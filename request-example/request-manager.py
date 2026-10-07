import os, sys

# Locate the sibling helper (service_token.py) so the import works in BOTH contexts:
#  - run as a script / %run  -> use this file's own folder (__file__ is set)
#  - copy/paste in a console  -> no __file__, so find the repo root (the folder
#    containing .git) from the cwd and point at request-example/.
if "__file__" in globals():
    _HELPERS = os.path.dirname(os.path.abspath(__file__))
else:
    _root = os.getcwd()
    while _root != os.path.dirname(_root) and not os.path.isdir(
        os.path.join(_root, ".git")
    ):
        _root = os.path.dirname(_root)
    _HELPERS = os.path.join(_root, "request-example")
sys.path.insert(0, _HELPERS)

import requests
from service_token import (
    get_service_token,
)  # client_credentials token (see service_token.py)
import time
s=time.time()
resp = requests.post(
    # "https://langraph-infrastructure.prod.mehes.gov.il/api/v1/agents/run",
    # "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
    # or this URL if you want to test with your local development:
    "http://localhost:8000/api/v1/agents/run",
    # headers={"Authorization": f"Bearer {get_service_token()}"},
    json={
        # "agent_name": "hsCode_classifier",
        "agent_name": "hscode_manager",
        "input_data": {
            # "message": "produt description: 'iphone 17'",
            # "enable_web_search":False,
            # "message": "Progressive distributorVEG 8/8-15/10RV with proximity switch N1-M12x1 right",
            #     # "message": 'The following is the product to classify. its a singele product. take all the description. ---beggining of product description---"Progressive distributorVEG 8/8-15/10RV with proximity switch N1-M12x1 right"---end of product descirption---'
            # "lead_document_title": "26044677970800"
            # "description": "BASIN",
            # "brand": "MAIDE IMPORT AND EXPORT TRADING CO., LIMITED",
            # "general_product": "Household basin",
            # "purpose": "for washing or holding liquids",
            "declaration_id": 593391658
        },
        # "input_data": {},
        "mode": "background",
    },
    verify=False,
)
print('took:', time.time()-s)
print(f"Status: {resp.status_code}")
r = resp.json()
import json

with open("tmp.json", "w") as f:
    f.write(json.dumps(r, ensure_ascii=False, indent=2))

print("./tmp.json")
