import logging
from app.utils.tracker import track_node_execution
from app.services.database_service import get_database_service
from app.nodes.hsCode_classifier.load_context import get_cached_data

logger = logging.getLogger(__name__)

TAX_FREE_CALCULATION = 'Tax Free'
MAX_HS_TREE_DEPTH = 7
DECLARATION_HS_CODES_PROCEDURE = 'dbo.get_DeclarationHSCodesByLeadDocumentID'


def _fetch_declared_hs_codes(declaration_id):
    """Fetch declared HS codes from DB for a given declaration.

    Calls the stored procedure and extracts FullClassification values.

    Returns:
        set[str] - unique declared HS codes, filtered for non-empty values.
    """
    db = get_database_service()
    if db is None:
        raise RuntimeError("Database service not available")

    result = db.read_dataframe_from_procedure(
        DECLARATION_HS_CODES_PROCEDURE, declaration_id
    )

    records = []
    if isinstance(result, dict) and 'data' in result:
        records = result['data']
    elif isinstance(result, list):
        for df_dict in result:
            if isinstance(df_dict, dict) and 'data' in df_dict:
                records.extend(df_dict['data'])

    hs_codes = set()
    for row in records:
        fc = row.get('FullClassification')
        if fc:
            hs_codes.add(str(fc))
    return hs_codes


def _hs_codes_to_items(hs_codes, fc_index):
    """Map HS codes to customs book items via the FC index.

    Returns:
        list[dict] - items found in the index (codes not found are skipped).
    """
    items = []
    for code in hs_codes:
        item = fc_index.get(code)
        if item:
            items.append(item)
    return items


def _collect_leaf_descendants(item_ids, customs_book_index):
    """BFS traversal to collect all leaf descendants of given item IDs.

    Uses the 'children' dict preserved on each item from the hierarchical
    JSON flattening (load_context.py appends original nodes by reference).

    Args:
        item_ids: set[str] of CustomsItemIDs to start from.
        customs_book_index: dict mapping CustomsItemID → item dict.

    Returns:
        list[dict] - all leaf items (IsLeaf == 1) found at or below the given IDs.
    """
    leaves = []
    visited = set()
    frontier = set(item_ids)

    for _ in range(MAX_HS_TREE_DEPTH + 1):
        if not frontier:
            break
        next_frontier = set()
        for item_id in frontier:
            if item_id in visited:
                continue
            visited.add(item_id)

            item = customs_book_index.get(str(item_id))
            if not item:
                continue

            if item.get('IsLeaf') == 1:
                leaves.append(item)

            children = item.get('children', {})
            if isinstance(children, dict):
                next_frontier.update(children.keys())

        frontier = next_frontier - visited

    return leaves


def _get_taxes_for_hs_codes(hs_codes, fc_index, customs_book_index):
    """Get (MasKnia, GeneralCustoms) tuples for a set of HS codes.

    Resolves codes to items, expands to leaf descendants, and collects
    tax values from leaves only.

    Returns:
        list[tuple[str, str]] - (MasKnia, GeneralCustoms) per leaf.
    """
    items = _hs_codes_to_items(hs_codes, fc_index)
    item_ids = {str(item.get('CustomsItemID')) for item in items if item.get('CustomsItemID')}
    leaves = _collect_leaf_descendants(item_ids, customs_book_index)
    return [
        (leaf.get('MasKnia'), leaf.get('GeneralCustoms'))
        for leaf in leaves
    ]


def _taxes_match(predicted_tax, declared_tax):
    """Check if a predicted tax tuple matches a declared tax tuple.

    A match is found when:
    - MasKnia values are equal, OR predicted MasKnia is Tax Free
    - AND GeneralCustoms values are equal, OR predicted GeneralCustoms is Tax Free
    """
    pred_knia, pred_customs = predicted_tax
    decl_knia, decl_customs = declared_tax
    knia_ok = (pred_knia == decl_knia) or (pred_knia == TAX_FREE_CALCULATION)
    customs_ok = (pred_customs == decl_customs) or (pred_customs == TAX_FREE_CALCULATION)
    return knia_ok and customs_ok


def _find_taxes_mismatch(declared_hs_codes, predicted_hs_codes, customs_book_index, fc_index):
    """Detect tax mismatch between declared and predicted HS codes.

    For each predicted HS code, expands to leaf descendants and checks if
    ANY of its tax values match ANY declaration tax value. If any predicted
    code has zero matches, returns True (mismatch detected).

    Returns:
        bool - True if a tax mismatch is detected.
    """
    declared_taxes = _get_taxes_for_hs_codes(declared_hs_codes, fc_index, customs_book_index)
    if not declared_taxes:
        return False

    for code in predicted_hs_codes:
        predicted_taxes = _get_taxes_for_hs_codes({code}, fc_index, customs_book_index)
        if not predicted_taxes:
            continue

        match_found = False
        for pred_tax in predicted_taxes:
            for decl_tax in declared_taxes:
                if _taxes_match(pred_tax, decl_tax):
                    match_found = True
                    break
            if match_found:
                break

        if not match_found:
            return True

    return False


def _get_confirmation_types(items):
    """Extract unique confirmation_type values from items' legal_requirements.

    Returns:
        set[str] - unique confirmation types.
    """
    types = set()
    for item in items:
        for req in item.get('legal_requirements', []):
            ct = req.get('confirmation_type')
            if ct is not None:
                types.add(ct)
    return types


def _find_requirements_mismatch(declared_hs_codes, predicted_hs_codes, fc_index):
    """Detect legal requirements mismatch between declared and predicted codes.

    Checks if predicted codes require permits/approvals that the declared
    codes do not cover. No descendant expansion — direct items only.

    Returns:
        tuple[bool, list[str]] - (mismatch detected, list of missing requirements).
    """
    declared_items = _hs_codes_to_items(declared_hs_codes, fc_index)
    predicted_items = _hs_codes_to_items(predicted_hs_codes, fc_index)

    declared_requirements = _get_confirmation_types(declared_items)
    predicted_requirements = _get_confirmation_types(predicted_items)

    missing = predicted_requirements - declared_requirements
    return bool(missing), sorted(missing)


@track_node_execution
def compare_declaration_node(state, reporter=None):
    """
    Layer 3.5: Compares predicted HS codes against declared HS codes.

    Detects tax mismatches and legal requirements mismatches between
    the classification results and the customs declaration in the DB.

    Reads:
        state['classification_results'] - List[Dict] from classify_products
        state['declaration_id'] - Optional[str] declaration reference

    Sets:
        state['comparison_results'] - Dict with comparison outcome, or None if skipped
    """
    state = state.copy()
    try:
        declaration_id = state.get('declaration_id')
        classification_results = state.get('classification_results', [])

        # --- Guard: no declaration_id ---
        if not declaration_id:
            reporter.action("No declaration_id — skipping declaration comparison")
            state['comparison_results'] = None
            state['error'] = None
            return state

        # --- Guard: no predicted HS codes ---
        predicted_hs_codes = set()
        for result in classification_results:
            if result:
                hs = result.get('hs_code')
                if hs:
                    predicted_hs_codes.add(str(hs))

        if not predicted_hs_codes:
            reporter.action("No predicted HS codes — skipping declaration comparison")
            state['comparison_results'] = None
            state['error'] = None
            return state

        reporter.action("Comparing predicted codes against declaration...")

        # 1. Fetch declared HS codes from DB
        declared_hs_codes = _fetch_declared_hs_codes(declaration_id)
        reporter.display(
            f"Declared HS codes: {len(declared_hs_codes)}, "
            f"Predicted: {len(predicted_hs_codes)}"
        )

        if not declared_hs_codes:
            reporter.action("No declared HS codes found — skipping comparison")
            state['comparison_results'] = None
            state['error'] = None
            return state

        # 2. Load customs book cache (already populated after classifier runs)
        cached = get_cached_data()
        customs_book_index = cached['customs_book_index']
        fc_index = cached['customs_book_fc_index']

        # 3. Tax comparison (with descendant expansion to leaves)
        taxes_mismatch = _find_taxes_mismatch(
            declared_hs_codes, predicted_hs_codes, customs_book_index, fc_index
        )

        # 4. Legal requirements comparison (direct items, no expansion)
        requirements_mismatch, missing_requirements = _find_requirements_mismatch(
            declared_hs_codes, predicted_hs_codes, fc_index
        )

        # Reporter output
        if taxes_mismatch:
            reporter.display("Tax mismatch detected between predicted and declared codes")
        else:
            reporter.display("No tax mismatch")

        if requirements_mismatch:
            reporter.display(f"Legal requirements mismatch: {', '.join(missing_requirements)}")
        else:
            reporter.display("No legal requirements mismatch")

        state['comparison_results'] = {
            'declaration_id': str(declaration_id),
            'taxes_mismatch': taxes_mismatch,
            'requirements_mismatch': requirements_mismatch,
            'predicted_hs_codes': sorted(predicted_hs_codes),
            'declared_hs_codes': sorted(declared_hs_codes),
            'missing_requirements': missing_requirements,
        }
        state['error'] = None

    except Exception as e:
        error_msg = f"Declaration comparison error: {str(e)}"
        logger.error(error_msg)
        reporter.error(error_msg)
        state['error'] = error_msg
        state['comparison_results'] = None
        if 'errors' not in state:
            state['errors'] = []
        state['errors'].append(error_msg)

    return state
