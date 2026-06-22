import json
import requests


def get_hs_code_from_description(description):
    response = requests.post(
        "http://localhost:8000/api/v1/agents/run",
        # "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
        json={
            "agent_name": "hscode_manager",
            # "input_data": {"declaration_id": 585326319},
            "input_data": {"lead_document_title": "26014632221711"},
            # "input_data": {"lead_document_title": "26044618816716"},
            # "input_data": {"lead_document_title": "26044620076739"},
            "username": "custom-moshed3",
            "mode": "background",
        },
        verify=False,
        timeout=1200,
    )
    response.raise_for_status()
    result = response.json()
    with open("tmp.json", "w") as f:
        f.write(json.dumps(result, ensure_ascii=0))
    return result["result"]["classification_summary"]["predicted_hs_code"]


if __name__ == "__main__":
    description = "fresh salmon"
    hs_code = get_hs_code_from_description(description)
    print(f"HS Code for '{description}': {hs_code}")
