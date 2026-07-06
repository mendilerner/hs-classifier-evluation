"""Explain, for a single run, why the correct HS code was NOT among the initial
candidates.

For every product it checks whether the expected code is covered by any initial
candidate. A candidate ``c`` covers expected ``e`` when one is a prefix of the
other (``e.startswith(c) or c.startswith(e)``): expected codes are not always
padded to 10 digits, so a plain ``e.startswith(c)`` would miss the correct leaf
whenever the candidate is the longer, zero-padded form. When the correct code is
not covered, the script diagnoses why by measuring the deepest HS level any
candidate reached toward the correct code:

    digits 0 -> no candidate even in the correct 2-digit chapter
    digits 2 -> correct chapter, but no candidate in the correct heading
    digits 4 -> correct heading, but no candidate in the correct subheading
    ... and so on.

Candidate data comes from the nested ``full_result`` blob via
``compare_runs.flatten`` (milvus_suggested_codes + llm_suggested_codes).

Usage:
    python candidates_miss_analysis.py            # analyses run 1
    python candidates_miss_analysis.py 2          # analyses run 2
    python candidates_miss_analysis.py 2 out.json # custom output file
"""

import json
import sys
from collections import Counter

from compare_runs import load_run, results_path, flatten

# Deepest correct-prefix length (in digits, floored to an even HS level) -> why
# the correct code fell out of the candidate set at that level.
LEVEL_REASON = {
    0: 'correct_chapter_not_in_candidates',       # wrong 2-digit chapter
    2: 'correct_heading_not_in_candidates',       # right chapter, wrong heading
    4: 'correct_subheading_not_in_candidates',    # right heading, wrong subheading
    6: 'correct_national_code_not_in_candidates',  # right 6-digit, wrong 8/10
    8: 'correct_leaf_not_in_candidates',          # right to 8 digits, wrong leaf
}


def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a or '', b or ''):
        if x == y:
            n += 1
        else:
            break
    return n


def candidate_codes(row):
    """Return (milvus_codes, llm_codes) as flat lists of candidate code strings."""
    milvus = [c[0] for c in (row.get('milvus_candidate_codes') or []) if c and c[0]]
    llm = [c for c in (row.get('llm_candidate_codes') or []) if c]
    return milvus, llm


def milvus_note(row, milvus_codes):
    """A contributing reason on the milvus side, when relevant."""
    if row.get('milvus_search_timeout'):
        return 'milvus_search_timed_out'
    if row.get('milvus_search_error') is not None:
        return f"milvus_search_error: {row.get('milvus_search_error')}"
    if not milvus_codes:
        return 'milvus_returned_no_candidates'
    return None


def analyze_row(row):
    """Return a case dict when the correct code is missing from candidates, else
    None."""
    expected = row.get('actual_code')
    if not expected:
        return None

    milvus_codes, llm_codes = candidate_codes(row)
    all_codes = milvus_codes + llm_codes

    # A candidate covers the correct code when either is a prefix of the other:
    # expected codes may be shorter than the zero-padded candidate leaf.
    if any(expected.startswith(c) or c.startswith(expected) for c in all_codes):
        return None  # correct code WAS in the candidates

    if not all_codes:
        if not row.get('did_server_responded', True):
            reason = 'no_server_response_no_candidates'
        elif row.get('success') is False:
            reason = 'classification_failed_no_candidates'
        else:
            reason = 'no_candidates_generated'
        deepest = None
        closest = []
    else:
        prefixes = [(c, common_prefix_len(c, expected)) for c in all_codes]
        best = max(p for _, p in prefixes)
        deepest = best - (best % 2)  # floor to an even HS level
        closest = sorted({c for c, p in prefixes if p == best})
        reason = LEVEL_REASON.get(deepest, LEVEL_REASON[8])

    return {
        'description': row.get('description'),
        'expected_code': expected,
        'reason': reason,
        'deepest_level_matched_digits': deepest,
        'closest_candidates': closest,
        'candidates_source': row.get('candidates_source'),
        'milvus_note': milvus_note(row, milvus_codes),
        'milvus_candidate_codes': row.get('milvus_candidate_codes'),
        'llm_candidate_codes': row.get('llm_candidate_codes'),
        'milvus_search': {
            'enabled': row.get('milvus_search_enabled'),
            'timeout': row.get('milvus_search_timeout'),
            'error': row.get('milvus_search_error'),
            'candidates_count': row.get('milvus_search_candidates_count'),
            'best_score': row.get('milvus_search_best_score'),
        },
        'predicted_code': row.get('predicted_code'),
        'predicted_digits_correct': row.get('are_given_digits_correct'),
    }


def metric_38_reconciliation(rows):
    """Reconcile with the test's metric 38, which measures the same idea but
    over a much narrower slice: only ``llm_direct`` rows, checking only
    ``llm_suggested_codes`` and ignoring milvus candidates. That inflates its
    miss rate (empty llm lists count as misses even when milvus retrieved the
    correct code), which is why its ~50% differs from this script's number.
    """
    llm_rows = [r for r in rows if r.get('candidates_source') == 'llm']
    manager_miss = [
        r for r in llm_rows if r.get('was_correct_code_in_candidates') is False
    ]
    # of the manager's "misses", how many did milvus actually cover?
    milvus_had_it = []
    for r in manager_miss:
        expected = r.get('actual_code') or ''
        milvus = [c[0] for c in (r.get('milvus_candidate_codes') or []) if c]
        if any(expected.startswith(c) or c.startswith(expected) for c in milvus):
            milvus_had_it.append(r)
    return {
        'note': (
            "metric 38 only checks llm_suggested_codes on llm_direct rows and "
            "ignores milvus candidates, over a smaller denominator; this script "
            "checks all candidates over all products."
        ),
        'llm_direct_rows': len(llm_rows),
        'metric_38_misses': len(manager_miss),
        'metric_38_miss_rate': (
            len(manager_miss) / len(llm_rows) if llm_rows else None
        ),
        'metric_38_misses_milvus_actually_had': len(milvus_had_it),
    }


def analyze(run_index, out_path):
    rows = [flatten(r) for r in load_run(run_index)]

    cases = [c for c in (analyze_row(r) for r in rows) if c is not None]

    reason_counts = {}
    for c in cases:
        reason_counts[c['reason']] = reason_counts.get(c['reason'], 0) + 1

    report = {
        'run_file': results_path(run_index),
        'criteria': (
            'expected code not covered by any initial candidate '
            '(milvus_suggested_codes + llm_suggested_codes), over all products'
        ),
        'summary': {
            'total_products': len(rows),
            'correct_missing_from_candidates': len(cases),
            'miss_rate': len(cases) / len(rows) if rows else None,
            'reason_counts': dict(
                sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)
            ),
            'misses_by_candidates_source': dict(
                Counter(c['candidates_source'] for c in cases)
            ),
            'metric_38_reconciliation': metric_38_reconciliation(rows),
        },
        'cases': cases,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    s = report['summary']
    m = s['metric_38_reconciliation']
    print(f'Analysed {results_path(run_index)}')
    print(f"  total products:                  {s['total_products']}")
    print(f"  correct missing from candidates: {s['correct_missing_from_candidates']}"
          f" ({s['miss_rate']:.0%} of all, milvus+llm)")
    print('  reasons:')
    for reason, count in s['reason_counts'].items():
        print(f'    {count:3d}  {reason}')
    print(f"  by candidates_source: {s['misses_by_candidates_source']}")
    print('  reconciliation with test metric 38 (llm_direct, llm codes only):')
    print(f"    {m['metric_38_misses']}/{m['llm_direct_rows']} "
          f"= {m['metric_38_miss_rate']:.0%} miss, but "
          f"{m['metric_38_misses_milvus_actually_had']} of those were actually "
          f"retrieved by milvus")
    print(f'\nDetailed report saved to {out_path}')


def main():
    args = sys.argv[1:]
    run_index = int(args[0]) if len(args) >= 1 else 1
    out_path = args[1] if len(args) >= 2 else f'candidates-miss-run{run_index}.json'
    analyze(run_index, out_path)


if __name__ == '__main__':
    main()
