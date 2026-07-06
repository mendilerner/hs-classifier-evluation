import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import json
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
import dotenv
import os
import hs_code_comparison
from hs_code_comparison import compare_hs_codes, load_customs_book

dotenv.load_dotenv()

urllib3.disable_warnings(InsecureRequestWarning)

RESULTS_JSON = 'agent-results.json'


username_for_agent = os.getenv("USERNAME_FOR_AGENT", "dev-user")

test_params = {
    'agent_url': os.getenv('AGENT_URL',
                           "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run"),
    'agent_name': os.getenv('AGENT_NAME', 'hscode_manager'),
    'threads_number': int(os.getenv('THREADS_NUMBER', '16')),
    'request_timeout_seconds': int(os.getenv('REQUEST_TIMEOUT_SECONDS', '600')),
    'model_used_for_candidates_generation': os.environ['MODEL_USED_FOR_CANDIDATES_GENERATION'],
    'model_used_for_process': os.environ['MODEL_USED_FOR_PROCESS']
}


def get_correct_until_level(predicted_code, actual_code):
    correct_until = 0
    for i in range(2, 11, 2):
        if predicted_code[:i] == actual_code[:i]:
            correct_until = i
        else:
            break
    return correct_until


def remove_even_trailing_zeros(code):
    zeros_removed = code.rstrip('0')
    return zeros_removed + '0' if len(zeros_removed) % 2 != 0 else zeros_removed


def query_agent(product_description):
    print('sending request. product description:', product_description)
    response = requests.post(
        test_params['agent_url'],
        json={
                "agent_name": test_params['agent_name'],
                "input_data": {
                    "message": product_description
                },
                "username": username_for_agent,
                "mode": "background"
            }
        ,

        verify=False,
        timeout=test_params['request_timeout_seconds'],
    )
    print('product:', product_description,
          'response.status_code:', response.status_code)
    with open('run-debug.jsonl', 'a') as f:
        f.write(response.text + '\n')
    response.raise_for_status()
    result = response.json()
    return result


def extract_classification(results):
    """Return (classification_summary, status) from either the hscode_manager
    response shape (result.classification_results[]) or the direct
    hsCode_classifier shape (flat result.classification_summary).

    Returns (None, None) when the manager extracted no products.
    """
    result = results['result']
    if 'classification_results' in result:
        classification_results = result.get('classification_results') or []
        if not classification_results:
            return None, None
        first = classification_results[0]
        return first['classification_summary'], first['classification_status']
    return result['classification_summary'], result['status']


def extract_candidate_info(results):
    """Return (milvus_codes, llm_codes, llm_stage_ran) from metadata (the fuller
    source; summary.llm_suggested_codes is often empty while metadata has it).

    Candidate generation runs server-side regardless of the final outcome, so
    this works for failed responses too. ``llm_stage_ran`` is False only when
    milvus short-circuited with a single leaf (classification_source ==
    'milvus_single_leaf'), i.e. the LLM never got to generate candidates — those
    rows must be excluded from LLM candidate recall.
    """
    result = results.get('result') or {}
    if 'classification_results' in result:
        crs = result.get('classification_results') or []
        entry = crs[0] if crs else {}
    else:
        entry = result
    summary = entry.get('classification_summary') or {}
    meta = (entry.get('classification_json') or {}).get('metadata') or {}
    milvus = [
        c.get('code')
        for c in (meta.get('milvus_suggested_codes') or [])
        if isinstance(c, dict) and c.get('code')
    ]
    llm = list(meta.get('llm_suggested_codes') or summary.get('llm_suggested_codes') or [])
    raw_candidates_source = summary.get('candidates_source') or meta.get('candidates_source')
    raw_classification_source = summary.get('classification_source') or meta.get('classification_source')
    llm_stage_ran = raw_classification_source != 'milvus_single_leaf'
    return milvus, llm, llm_stage_ran, raw_candidates_source, raw_classification_source


def _code_covers(candidate, expected):
    """A candidate covers the correct code when either is a prefix of the other
    (expected codes aren't always padded to 10 digits)."""
    return bool(candidate) and bool(expected) and (
        expected.startswith(candidate) or candidate.startswith(expected)
    )


def correct_in_candidates(codes, expected):
    """True/False if any candidate covers expected; None when the generator
    produced no candidates."""
    if not codes:
        return None
    return any(_code_covers(c, expected) for c in codes)


def candidate_fields(results, expected_code):
    """Candidate-recall fields, computed for every row (success or failure)
    since candidate generation runs regardless of the final classification.
    Evaluated over the whole dataset — no candidates / errors count as misses.
    """
    milvus, llm, llm_stage_ran, raw_candidates_source, raw_classification_source = extract_candidate_info(results)
    correct_in_milvus = correct_in_candidates(milvus, expected_code)
    correct_in_llm = correct_in_candidates(llm, expected_code)
    return {
        # routing / distribution — populated for every row (candidate
        # generation runs regardless of the final outcome)
        'candidates_source': ('milvus' if raw_candidates_source == 'milvus' else 'llm') if raw_candidates_source else None,
        'classification_source': ('milvus' if raw_classification_source == 'milvus_single_leaf' else 'llm') if raw_classification_source else None,
        'correct_in_milvus_candidates': correct_in_milvus,
        'correct_in_llm_candidates': correct_in_llm,
        'correct_in_any_candidate': (correct_in_milvus is True) or (correct_in_llm is True),
        'llm_candidate_stage_ran': llm_stage_ran,
    }


def identify_product(product):
    description = product['description']
    expected_code = product['expected_code']
    try:
        results = query_agent(description)
    except Exception as e:
        print('Error querying agent for product:', product, 'Error:', str(e))
        # Server never answered: no candidates at all -> counts as a miss.
        return {
            'description': description,
            'did_server_responded': False,
            'actual_code': expected_code,
            'correct_in_milvus_candidates': None,
            'correct_in_llm_candidates': None,
            'correct_in_any_candidate': False,
            'llm_candidate_stage_ran': True,
        }
    if results['success'] == False:
        print('Agent returned unsuccessful result for product:',
              product, 'Result:', results)
        return {
            'description': description,
            'did_server_responded': True,
            'success': False,
            'actual_code': expected_code,
            'full_result': results,
            **candidate_fields(results, expected_code),
        }

    summary, status = extract_classification(results)
    if not summary or not summary.get('predicted_hs_code'):
        print('Manager returned no usable classification for product:',
              product, 'Result:', results)
        return {
            'description': description,
            'did_server_responded': True,
            'success': False,
            'actual_code': expected_code,
            'full_result': json.dumps(results),
            **candidate_fields(results, expected_code),
        }

    predicted_hs_code = summary['predicted_hs_code']

    code_comparison = compare_hs_codes(predicted_hs_code, product['expected_code'])

    return {
        'description': description,
        'did_server_responded': True,
        'success': True,
        'predicted_code': predicted_hs_code,
        'actual_code': product['expected_code'],
        'did_found_leaf': summary['is_leaf'],
        'status': status,
        'length_of_predicted_code': len(remove_even_trailing_zeros(predicted_hs_code)) if not summary['is_leaf'] else 10,
        'are_given_digits_correct': predicted_hs_code[:len(remove_even_trailing_zeros(predicted_hs_code))] == product['expected_code'][:len(remove_even_trailing_zeros(predicted_hs_code))],
        'correct_until': get_correct_until_level(predicted_hs_code, product['expected_code']),
        **candidate_fields(results, expected_code),
        'server_run_time_minutes': summary['total_runtime_minutes'],
        'llm_calls_count': summary['total_llm_calls'],
        'total_input_tokens': results['token_usage']['total_input_tokens'] if results['token_usage'] else 0,
        'total_output_tokens': results['token_usage']['total_output_tokens'] if results['token_usage'] else 0,
        'full_result': json.dumps(results),
        'mas_knia_mismatch': code_comparison['mas_knia_mismatch'],
        'general_customs_mismatch': code_comparison['general_customs_mismatch'],
        'requirements_mismatch': code_comparison['requirements_mismatch'],
        'any_leaf_full_match': code_comparison['any_leaf_full_match'],
    }


def _build_comparison_metrics(success_df):
    """Build tax and legal-requirements comparison metrics over the success
    subset (rows that produced a final HS code), for rows with non-null
    comparison values.
    """
    comparison_ok = (
        success_df['mas_knia_mismatch'].notna()
        & success_df['general_customs_mismatch'].notna()
        & success_df['requirements_mismatch'].notna()
        & success_df['any_leaf_full_match'].notna()
    )
    subset = success_df[comparison_ok]
    if len(subset) == 0:
        return {
            '34_mas_knia_mismatch_rate': float('nan'),
            '35_general_customs_mismatch_rate': float('nan'),
            '36_requirements_mismatch_rate': float('nan'),
            '37_no_tax_or_requirements_mismatch_rate': float('nan'),
        }
    return {
        '34_mas_knia_mismatch_rate': subset['mas_knia_mismatch'].astype(float).mean(),
        '35_general_customs_mismatch_rate': subset['general_customs_mismatch'].astype(float).mean(),
        '36_requirements_mismatch_rate': subset['requirements_mismatch'].astype(float).mean(),
        '37_no_tax_or_requirements_mismatch_rate': subset['any_leaf_full_match'].astype(float).mean(),
    }


NUM_RUNS = 3


def run_once(test_data, run_index, executor):
    """Query the agent for every product once and return the results DataFrame.

    Uses the shared executor so concurrency persists across iterations; the
    map call blocks until this iteration's last response before returning.
    Results are cached per run so a rerun can reuse a completed run.
    """
    results_json = RESULTS_JSON.replace('.json', f'-run{run_index}.json')

    if os.path.exists(results_json):
        print(f'Loading existing results from {results_json}, skipping agent run...')
        with open(results_json) as f:
            result_list = json.load(f)
    else:
        print(f'Run {run_index}/{NUM_RUNS}: querying agent for all products...')
        result_list = list(executor.map(identify_product, test_data.to_dict(orient='records')))

        with open(results_json, 'w', encoding='utf-8') as f:
            json.dump(result_list, f, indent=2, default=lambda x: None)
        print(f'Agent results saved to {results_json}')

    results_df = pd.DataFrame(result_list)
    results_df.to_csv(f'classification-results-run{run_index}.csv')
    return results_df


def compute_metrics(results_df):
    # success = a final HS code was produced. identify_product sets success=True
    # only when predicted_hs_code exists (NEEDS_CLARIFICATION rows carry a code
    # and count as success). Every correctness / distribution metric below is
    # computed over this success subset only.
    success_df = results_df[results_df['success'] == True]
    n_total = len(results_df)
    n_success = len(success_df)

    return {
        '01_total_tests_count': n_total,

        '02_success_rate': n_success / n_total,
        '03_failure_rate': (n_total - n_success) / n_total,
        '25_failure_count': n_total - n_success,

        # length-distribution rates over ALL products; correctness within each
        # bucket (05/06/...) over the success subset
        '04_response_with_2_digits_rate': (results_df['length_of_predicted_code'] == 2).mean(),
        '05_correct_when_return_2_rate': success_df[(success_df['length_of_predicted_code'] == 2)]['are_given_digits_correct'].mean(),
        '06_average_correct_digits_when_return_2': success_df[success_df['length_of_predicted_code'] == 2]['correct_until'].mean(),
        '07_response_with_4_digits_rate': (results_df['length_of_predicted_code'] == 4).mean(),
        '08_correct_when_return_4_rate': success_df[(success_df['length_of_predicted_code'] == 4)]['are_given_digits_correct'].mean(),
        '09_average_correct_digits_when_return_4': success_df[success_df['length_of_predicted_code'] == 4]['correct_until'].mean(),
        '10_response_with_6_digits_rate': (results_df['length_of_predicted_code'] == 6).mean(),
        '11_correct_when_return_6_rate': success_df[success_df['length_of_predicted_code'] == 6]['are_given_digits_correct'].mean(),
        '12_average_correct_digits_when_return_6': success_df[success_df['length_of_predicted_code'] == 6]['correct_until'].mean(),
        '13_response_with_8_digits_rate': (results_df['length_of_predicted_code'] == 8).mean(),
        '14_correct_when_return_8_rate': success_df[success_df['length_of_predicted_code'] == 8]['are_given_digits_correct'].mean(),
        '15_average_correct_digits_when_return_8': success_df[success_df['length_of_predicted_code'] == 8]['correct_until'].mean(),
        '16_response_with_10_digits_rate': (results_df['length_of_predicted_code'] == 10).mean(),
        '17_correct_when_return_10_rate': success_df[success_df['length_of_predicted_code'] == 10]['are_given_digits_correct'].mean(),
        '18_average_correct_digits_when_return_10': success_df[success_df['length_of_predicted_code'] == 10]['correct_until'].mean(),

        # candidate-source / classification-source routing over ALL products
        '19_candidates_from_milvus_rate': (results_df['candidates_source'] == 'milvus').mean(),
        '20_candidate_from_llm_rate': (results_df['candidates_source'] == 'llm').mean(),

        '21_classification_from_milvus_rate': (results_df['classification_source'] == 'milvus').mean(),
        '22_classification_from_llm_rate': (results_df['classification_source'] == 'llm').mean(),

        '23_candidate_from_milvus_and_classification_from_llm_rate': ((results_df['candidates_source'] == 'milvus') & (results_df['classification_source'] == 'llm')).mean(),

        '27_correct_response_rate_when_classification_from_milvus': success_df[success_df['classification_source'] == 'milvus']['are_given_digits_correct'].mean(),
        '28_correct_response_rate_when_classification_from_llm': success_df[success_df['classification_source'] == 'llm']['are_given_digits_correct'].mean(),
        '29_correct_response_rate_when_candidates_from_milvus_and_classification_from_llm': success_df[(success_df['candidates_source'] == 'milvus') & (success_df['classification_source'] == 'llm')]['are_given_digits_correct'].mean(),

        '30_average_server_run_time_minutes_for_successful_responses': success_df['server_run_time_minutes'].mean(),
        '31_average_llm_calls_count_for_successful_responses': success_df['llm_calls_count'].mean(),
        '32_average_total_input_tokens_for_successful_responses': success_df['total_input_tokens'].mean(),
        '33_average_total_output_tokens_for_successful_responses': success_df['total_output_tokens'].mean(),

        '39_correct_response_rate_overall': success_df['are_given_digits_correct'].mean(),

        # --- candidate-generation recall: measured over the WHOLE dataset
        # (failed / errored / no-candidate rows are misses), since candidate
        # generation runs regardless of the final classification outcome. ---
        '38_correct_in_any_candidate_rate': (results_df['correct_in_any_candidate'] == True).mean(),
        # milvus always runs, so its recall is over every row
        '40_correct_in_milvus_candidates_rate': (results_df['correct_in_milvus_candidates'] == True).mean(),
        # the LLM only generates candidates when milvus did not short-circuit
        # with a single leaf; exclude those rows from LLM recall
        '41_correct_in_llm_candidates_rate': (results_df[results_df['llm_candidate_stage_ran'] == True]['correct_in_llm_candidates'] == True).mean(),

        **_build_comparison_metrics(success_df),
    }


def main():
    print('Starting classifier test with url:', test_params['agent_url'], 'using agent:',
          test_params['agent_name'], 'with', test_params['threads_number'], 'threads and', test_params['request_timeout_seconds'], 'seconds timeout per request.')
    print(f'Running the test {NUM_RUNS} times and averaging the metrics.')

    with open('./classified-data-input.csv') as f:
        test_data = pd.read_csv(f,
                                index_col='Unnamed: 0',
                                dtype=str
                                )

    print('Loading customs book index...')
    load_customs_book()

    per_run_metrics = []
    # One shared executor across all iterations so its threads persist between
    # runs; each iteration still blocks until its last response.
    with ThreadPoolExecutor(max_workers=test_params['threads_number']) as executor:
        for run_index in range(1, NUM_RUNS + 1):
            results_df = run_once(test_data, run_index, executor)
            per_run_metrics.append(compute_metrics(results_df))

    per_run_df = pd.DataFrame(per_run_metrics, index=[f'run{i}' for i in range(1, NUM_RUNS + 1)])
    per_run_df.to_csv('metrics-per-run.csv')

    avg_metrics = per_run_df.mean(numeric_only=True).to_dict()
    pd.DataFrame([avg_metrics]).to_csv('metrics.csv', index=False)

    print(f'\nAveraged metrics over {NUM_RUNS} runs:')
    for key, value in avg_metrics.items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    main()
