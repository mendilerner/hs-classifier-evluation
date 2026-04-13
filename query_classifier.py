import requests


def get_hs_code_from_description(description):
    response = requests.post(
        "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
        json={
            "agent_name": "hsCode_classifier",
            "input_data": {"message": description},
            "username": "dev-user",
            "mode": "background"
        },
        verify=False,
        timeout=600
    )
    response.raise_for_status()
    result = response.json()
    return result['result']['classification_summary']['predicted_hs_code']


if __name__ == "__main__":
    description = 'macbook pro 16 inch'
    hs_code = get_hs_code_from_description(description)
    print(f"HS Code for '{description}': {hs_code}")
