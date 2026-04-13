from concurrent.futures import ThreadPoolExecutor
import json
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning


urllib3.disable_warnings(InsecureRequestWarning)


AGENT_URL = "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run"
AGENT_NAME = "hsCode_classifier"
USERNAME = "custom-moshed3"
THREADS_NUMBER = 16
REQUEST_TIMEOUT_SECONDS = 600


def query_agent(product_description):
    print('Sending request for product:', product_description)
    payload = {
        "agent_name": AGENT_NAME,
        "input_data": {
            "message": product_description
        },
        "username": USERNAME,
        "mode": "background"
    }
    response = requests.post(
        AGENT_URL,
        json=payload,
        verify=False,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    print('Response status:', response.status_code)
    if response.status_code >= 400:
        print('Response body:', response.text)
    response.raise_for_status()
    result = response.json()
    return result


def classify_product(description):
    try:
        results = query_agent(description)
    except Exception as e:
        print(f'Error querying agent for product "{description}": {str(e)}')
        return {
            'description': description,
            'success': False,
            'error': str(e)
        }

    if not results.get('success'):
        print(f'Agent returned unsuccessful result for "{description}"')
        return {
            'description': description,
            'success': False,
            'result': results
        }

    predicted_hs_code = results['result']['classification_summary']['predicted_hs_code']

    return {
        'description': description,
        'success': True,
        'predicted_hs_code': predicted_hs_code,
        'is_leaf': results['result']['classification_summary']['is_leaf'],
        'status': results['result']['status'],
        'candidates_source': results['result']['classification_summary'].get('candidates_source'),
        'classification_source': results['result'].get('classification_source'),
        'full_result': results
    }


def classify_descriptions(descriptions):
    with ThreadPoolExecutor(max_workers=THREADS_NUMBER) as executor:
        results = list(executor.map(classify_product, descriptions))

    return results


if __name__ == '__main__':
    example_descriptions = [
        "Steel bolts and nuts",
        "Cotton t-shirt",
        "Laptop computer"
    ]

    results = classify_descriptions(example_descriptions)

    print(f'\nResults:')
    for result in results:
        if result['success']:
            print(f"  {result['description']}: {result['predicted_hs_code']}")
        else:
            print(
                f"  {result['description']}: Error - {result.get('error', 'Unknown')}")
