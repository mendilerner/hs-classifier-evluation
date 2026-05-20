import json
import requests

def get_hs_code_from_description(description):
    response = requests.post(
        "http://localhost:8000/api/v1/agents/run",
        json={
            "agent_name": "hsCode_classifier",
            "input_data": {"message": description},
            "username": "custom-moshed3",
            "mode": "background"
        },
        verify=False,
        timeout=600
    )
    response.raise_for_status()
    result = response.json()
    with open('tmp.json', 'w') as f:
        f.write(json.dumps(result, ensure_ascii=0))
    return result['result']['classification_summary']['predicted_hs_code']


if __name__ == "__main__":
    description = 'alovera juice 100% pure'
    hs_code = get_hs_code_from_description(description)
    print(f"HS Code for '{description}': {hs_code}")
