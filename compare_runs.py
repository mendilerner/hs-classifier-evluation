"""Compare per-product classification results between two runs and save the
root cause of every difference to a JSON file.

The classifier is non-deterministic, so running the same input twice can yield
different HS codes. This script pairs each product across two run files
(``agent-results-run{i}.json`` produced by ``main_no_ml_flow.py``), detects
which fields changed, and attributes a likely root cause so the differences can
be investigated.

Usage:
    python compare_runs.py                 # compares run 1 vs run 2
    python compare_runs.py 1 3             # compares run 1 vs run 3
    python compare_runs.py 1 2 out.json    # custom output file
"""

import json
import sys

RESULTS_JSON = 'agent-results.json'

# Fields whose change counts as a real difference worth reporting. These come
# from two places: the flat per-product result row, and (for the *_ prefixed
# candidate / milvus / web-enrichment fields) the nested ``full_result`` blob,
# which ``flatten`` merges in before comparison.
DIFF_FIELDS = [
    'predicted_code',
    'are_given_digits_correct',
    'correct_until',
    'length_of_predicted_code',
    'did_found_leaf',
    'status',
    'success',
    'did_server_responded',
    'candidates_source',
    'classification_source',
    'was_correct_code_in_candidates',
    'mas_knia_mismatch',
    'general_customs_mismatch',
    'requirements_mismatch',
    'any_leaf_full_match',
    # --- extracted from the nested full_result blob ---
    'initial_candidates_count',
    'milvus_candidate_codes',
    'llm_candidate_codes',
    'milvus_search_enabled',
    'milvus_search_timeout',
    'milvus_search_error',
    'milvus_search_candidates_count',
    'milvus_search_best_score',
    'web_enrichment_present',
]

# Fields shown for context only; their changes are expected noise (counts,
# timings) and never trigger a difference on their own.
INFO_FIELDS = [
    'llm_calls_count',
    'server_run_time_minutes',
    'total_input_tokens',
    'total_output_tokens',
    'web_enrichment',
]


def results_path(run_index):
    return RESULTS_JSON.replace('.json', f'-run{run_index}.json')


def load_run(run_index):
    with open(results_path(run_index), encoding='utf-8') as f:
        return json.load(f)


def _parse_full_result(row):
    """full_result may be a JSON string (success rows), an already-parsed dict
    (success=False rows), or absent (error / no-response rows)."""
    fr = row.get('full_result')
    if isinstance(fr, dict):
        return fr
    if isinstance(fr, str):
        try:
            return json.loads(fr)
        except (ValueError, TypeError):
            return None
    return None


def extract_details(row):
    """Pull the nested candidate / milvus-search / web-enrichment fields out of
    the raw full_result blob. Returns {} when full_result is missing or
    unparseable, so those rows simply compare as ``None`` on the deep fields.
    """
    fr = _parse_full_result(row)
    if not fr:
        return {}

    result = fr.get('result') or {}
    cr = result.get('classification_results')
    entry = cr[0] if cr else None
    if entry is not None:  # hscode_manager response shape
        summary = entry.get('classification_summary') or {}
        cj = entry.get('classification_json') or {}
        web = entry.get('web_enrichment')
    else:  # direct hsCode_classifier response shape
        summary = result.get('classification_summary') or {}
        cj = result.get('classification_json') or {}
        web = None

    meta = cj.get('metadata') or {}
    milvus = meta.get('milvus_integration') or {}

    milvus_codes = [
        [c.get('code'), c.get('score')]
        for c in (meta.get('milvus_suggested_codes') or [])
        if isinstance(c, dict)
    ]
    llm_codes = list(
        summary.get('llm_suggested_codes')
        or meta.get('llm_suggested_codes')
        or []
    )

    return {
        'initial_candidates_count': summary.get(
            'initial_candidates_count', meta.get('initial_candidates_count')
        ),
        'milvus_candidate_codes': milvus_codes,
        'llm_candidate_codes': llm_codes,
        'milvus_search_enabled': milvus.get('enabled'),
        'milvus_search_timeout': milvus.get('timeout'),
        'milvus_search_error': milvus.get('error'),
        'milvus_search_candidates_count': milvus.get('candidates_count'),
        'milvus_search_best_score': milvus.get('best_score'),
        'web_enrichment_present': web is not None,
        'web_enrichment': web,
    }


def flatten(row):
    """Merge the flat result row with the deep full_result fields into a single
    dict that the comparison operates on. full_result itself is dropped."""
    flat = {k: v for k, v in row.items() if k != 'full_result'}
    flat.update(extract_details(row))
    return flat


def _milvus_code_set(row):
    return {c[0] for c in (row.get('milvus_candidate_codes') or [])}


def changed_fields(a, b):
    """Return the DIFF_FIELDS whose value differs between rows a and b."""
    return [f for f in DIFF_FIELDS if a.get(f) != b.get(f)]


def diagnose_root_cause(a, b):
    """Attribute the most likely root cause of the difference.

    Returns (primary_cause, [contributing_factors]). The checks are ordered
    along the classification pipeline, from the earliest stage (did the server
    even answer?) through candidate retrieval (milvus search, initial
    candidates, web enrichment) to the final classification decision and pure
    model non-determinism. The primary cause is the most upstream factor, since
    an upstream change is what propagates into everything downstream.
    """
    factors = []

    if a.get('did_server_responded') != b.get('did_server_responded'):
        factors.append('server_response_availability_changed')
    if a.get('success') != b.get('success'):
        factors.append('success_flag_changed')

    # --- web enrichment: the first classification step, it enriches the
    # description before any candidate retrieval, so a change here is upstream
    # of everything below. ---
    if a.get('web_enrichment_present') != b.get('web_enrichment_present'):
        factors.append('web_enrichment_changed')

    # --- candidate retrieval stage ---
    if (a.get('milvus_search_enabled') != b.get('milvus_search_enabled')
            or a.get('milvus_search_timeout') != b.get('milvus_search_timeout')
            or (a.get('milvus_search_error') is None)
            != (b.get('milvus_search_error') is None)):
        factors.append('milvus_search_status_changed')

    if _milvus_code_set(a) != _milvus_code_set(b):
        factors.append('initial_candidates_changed')
    elif a.get('milvus_candidate_codes') != b.get('milvus_candidate_codes'):
        # Same milvus codes, different scores/order.
        factors.append('milvus_candidate_scores_changed')
    elif a.get('initial_candidates_count') != b.get('initial_candidates_count'):
        factors.append('initial_candidates_count_changed')

    if a.get('llm_candidate_codes') != b.get('llm_candidate_codes'):
        factors.append('llm_suggested_candidates_changed')

    if a.get('candidates_source') != b.get('candidates_source'):
        factors.append(
            'candidate_retrieval_path_changed '
            f"({a.get('candidates_source')} -> {b.get('candidates_source')})"
        )
    if a.get('was_correct_code_in_candidates') != b.get(
        'was_correct_code_in_candidates'
    ):
        factors.append('correct_code_presence_in_candidates_changed')

    # --- classification decision stage ---
    if a.get('classification_source') != b.get('classification_source'):
        factors.append(
            'classification_path_changed '
            f"({a.get('classification_source')} -> "
            f"{b.get('classification_source')})"
        )
    if a.get('status') != b.get('status'):
        factors.append(
            f"status_changed ({a.get('status')} -> {b.get('status')})"
        )
    if a.get('did_found_leaf') != b.get('did_found_leaf'):
        factors.append('leaf_resolution_changed')

    # The primary cause is the most upstream contributing factor, if any.
    if factors:
        primary = factors[0]
    elif a.get('predicted_code') != b.get('predicted_code'):
        # Identical pipeline decisions and candidate sets but a different code:
        # the model produced different output for identical inputs.
        primary = 'llm_non_determinism_same_pipeline'
    else:
        primary = 'other'

    return primary, factors


def field_delta(a, b, fields):
    """Return {field: {'run_a':.., 'run_b':..}} for fields that differ."""
    delta = {}
    for f in fields:
        if a.get(f) != b.get(f):
            delta[f] = {'run_a': a.get(f), 'run_b': b.get(f)}
    return delta


def compare(run_a, run_b, out_path):
    list_a = load_run(run_a)
    list_b = load_run(run_b)

    # Both runs classify the same input CSV in the same order, so products are
    # paired by position. Descriptions can repeat, so keying by description
    # would drop rows; positional pairing keeps every product.
    if len(list_a) != len(list_b):
        print(
            f'WARNING: run lengths differ ({len(list_a)} vs {len(list_b)}); '
            'pairing by position up to the shorter run.'
        )

    differences = []
    misaligned = []
    root_cause_counts = {}
    correctness_flipped = 0
    predicted_code_changed = 0

    for row_a, row_b in zip(list_a, list_b):
        a = flatten(row_a)
        b = flatten(row_b)

        if a.get('description') != b.get('description'):
            misaligned.append(
                {'run_a': a.get('description'), 'run_b': b.get('description')}
            )

        changed = changed_fields(a, b)
        if not changed:
            continue

        primary, factors = diagnose_root_cause(a, b)
        root_cause_counts[primary] = root_cause_counts.get(primary, 0) + 1

        if a.get('predicted_code') != b.get('predicted_code'):
            predicted_code_changed += 1
        if a.get('are_given_digits_correct') != b.get('are_given_digits_correct'):
            correctness_flipped += 1

        differences.append({
            'description': a.get('description'),
            'actual_code': a.get('actual_code'),
            'root_cause': primary,
            'contributing_factors': factors,
            'correctness_flipped': (
                a.get('are_given_digits_correct')
                != b.get('are_given_digits_correct')
            ),
            'changed_fields': changed,
            'changes': field_delta(a, b, DIFF_FIELDS),
            'context': field_delta(a, b, INFO_FIELDS),
        })

    report = {
        'run_a_file': results_path(run_a),
        'run_b_file': results_path(run_b),
        'summary': {
            'products_in_run_a': len(list_a),
            'products_in_run_b': len(list_b),
            'products_compared': min(len(list_a), len(list_b)),
            'products_with_differences': len(differences),
            'predicted_code_changed': predicted_code_changed,
            'correctness_flipped': correctness_flipped,
            'misaligned_pairs': misaligned,
            'root_cause_counts': dict(
                sorted(root_cause_counts.items(),
                       key=lambda kv: kv[1], reverse=True)
            ),
        },
        'differences': differences,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    s = report['summary']
    print(f'Compared {results_path(run_a)} vs {results_path(run_b)}')
    print(f"  products compared:        {s['products_compared']}")
    print(f"  products with differences: {s['products_with_differences']}")
    print(f"  predicted_code changed:    {s['predicted_code_changed']}")
    print(f"  correctness flipped:       {s['correctness_flipped']}")
    print('  root causes:')
    for cause, count in s['root_cause_counts'].items():
        print(f'    {count:3d}  {cause}')
    print(f'\nDetailed report saved to {out_path}')


def main():
    args = sys.argv[1:]
    run_a = int(args[0]) if len(args) >= 1 else 1
    run_b = int(args[1]) if len(args) >= 2 else 2
    out_path = args[2] if len(args) >= 3 else f'run-comparison-run{run_a}-vs-run{run_b}.json'
    compare(run_a, run_b, out_path)


if __name__ == '__main__':
    main()
