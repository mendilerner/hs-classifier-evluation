"""
Utilities for comparing HS codes (predicted vs actual) by looking up
tax rates and legal requirements from the customs book hierarchical JSON.

Both comparisons are bidirectional: a mismatch is reported when either
side has values the other side does not cover.
"""

import json
import os

MAX_HS_TREE_DEPTH = 7

_cached_data = None


def _flatten_item(item, customs_book_index, fc_index, parent_index, parent_id=None):
    """Recursively index a customs book item and all its descendants."""
    item_id = str(item.get('CustomsItemID', ''))
    fc = item.get('CI_BaseFullClassification', '')
    if item_id:
        customs_book_index[item_id] = item
        if parent_id is not None:
            parent_index[item_id] = parent_id
    if fc:
        fc_index[fc] = item
    children = item.get('children', {})
    if isinstance(children, dict):
        for child in children.values():
            _flatten_item(child, customs_book_index, fc_index, parent_index, item_id)


def load_customs_book(json_path=None):
    """Load and index customs_book_hierarchical.json.  Result is module-level cached."""
    global _cached_data
    if _cached_data is not None:
        return _cached_data
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'customs_book_hierarchical.json',
        )
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    customs_book_index = {}
    fc_index = {}
    parent_index = {}
    for top_item in data.get('customs_book', {}).values():
        _flatten_item(top_item, customs_book_index, fc_index, parent_index)
    _cached_data = {
        'customs_book_index': customs_book_index,
        'fc_index': fc_index,
        'parent_index': parent_index,
    }
    return _cached_data


def _is_item_ancestor(ancestor_id, descendant_id, parent_index):
    """Return True if ancestor_id appears in the parent chain of descendant_id."""
    current = parent_index.get(str(descendant_id))
    while current is not None:
        if current == str(ancestor_id):
            return True
        current = parent_index.get(current)
    return False


def _collect_leaf_descendants(item_ids, customs_book_index):
    """BFS traversal that collects all leaf items reachable from the given IDs."""
    leaves = []
    visited = set()
    frontier = {str(i) for i in item_ids}
    for _ in range(MAX_HS_TREE_DEPTH + 1):
        if not frontier:
            break
        next_frontier = set()
        for item_id in frontier:
            if item_id in visited:
                continue
            visited.add(item_id)
            item = customs_book_index.get(item_id)
            if not item:
                continue
            if item.get('IsLeaf') == 1:
                leaves.append(item)
            children = item.get('children', {})
            if isinstance(children, dict):
                next_frontier.update(str(k) for k in children.keys())
        frontier = next_frontier - visited
    return leaves


def _get_leaf_profiles(hs_code, fc_index, customs_book_index):
    """Return a frozenset of (MasKnia, GeneralCustoms, frozenset(requirements)) tuples
    for every leaf descendant of the given HS code.

    Returns None if the code is not found in the index or has no leaves.
    """
    item = fc_index.get(hs_code)
    if not item:
        return None
    item_id = str(item.get('CustomsItemID', ''))
    if not item_id:
        return None
    leaves = _collect_leaf_descendants({item_id}, customs_book_index)
    if not leaves:
        return None
    return frozenset(
        (
            leaf.get('MasKnia'),
            leaf.get('GeneralCustoms'),
            frozenset(
                req['confirmation_type']
                for req in leaf.get('legal_requirements', [])
                if req.get('confirmation_type') is not None
            ),
        )
        for leaf in leaves
    )


def compare_hs_codes(predicted_code, actual_code):
    """Compare a predicted HS code against the actual HS code.

    Four cases based on the hierarchy relationship between the two codes:

    1. Predicted is ancestor of actual
       → no mismatch (classifier was less specific but in the right branch)

    2. Actual is ancestor of predicted
       → mismatch if any leaf of actual differs from predicted
         (actual is ambiguous; its range includes leaves with different taxes)

    3. Both are leaves
       → direct equality comparison

    4. One or both are branches, neither is ancestor of the other
       → match only if both expand to the exact same leaf set

    Returns:
        dict with keys:
            'mas_knia_mismatch'        – bool, or None if either code is unknown
            'general_customs_mismatch' – bool, or None if either code is unknown
            'requirements_mismatch'    – bool, or None if either code is unknown
            'any_leaf_full_match'      – bool, or None if either code is unknown
    """
    cached = load_customs_book()
    fc_index = cached['fc_index']
    customs_book_index = cached['customs_book_index']
    parent_index = cached['parent_index']

    predicted_profiles = _get_leaf_profiles(predicted_code, fc_index, customs_book_index)
    actual_profiles = _get_leaf_profiles(actual_code, fc_index, customs_book_index)

    if predicted_profiles is None or actual_profiles is None:
        return {
            'mas_knia_mismatch': None,
            'general_customs_mismatch': None,
            'requirements_mismatch': None,
            'any_leaf_full_match': None,
        }

    pred_item = fc_index.get(predicted_code)
    act_item = fc_index.get(actual_code)
    pred_id = str(pred_item.get('CustomsItemID', ''))
    act_id = str(act_item.get('CustomsItemID', ''))

    pred_is_ancestor = _is_item_ancestor(pred_id, act_id, parent_index)

    pred_mas_knia = frozenset(p[0] for p in predicted_profiles)
    act_mas_knia = frozenset(p[0] for p in actual_profiles)
    pred_gc = frozenset(p[1] for p in predicted_profiles)
    act_gc = frozenset(p[1] for p in actual_profiles)
    pred_reqs = frozenset(p[2] for p in predicted_profiles)
    act_reqs = frozenset(p[2] for p in actual_profiles)

    if pred_is_ancestor:
        # Case 1: predicted ancestor of actual → no mismatch
        return {
            'mas_knia_mismatch': False,
            'general_customs_mismatch': False,
            'requirements_mismatch': False,
            'any_leaf_full_match': True,
        }

    # Cases 2, 3 & 4: actual ancestor of predicted, both leaves, or different branches
    # No mismatch only when each dimension resolves to a single unambiguous value
    # AND that value is identical on both sides. If either side has multiple possible
    # values (branch with diverse leaves), there is a risk of fiscal mismatch.
    return {
        'mas_knia_mismatch': not (len(act_mas_knia) == 1 and act_mas_knia == pred_mas_knia),
        'general_customs_mismatch': not (len(act_gc) == 1 and act_gc == pred_gc),
        'requirements_mismatch': not (len(act_reqs) == 1 and act_reqs == pred_reqs),
        'any_leaf_full_match': len(actual_profiles) == 1 and actual_profiles == predicted_profiles,
    }
