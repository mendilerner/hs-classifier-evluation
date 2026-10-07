"""Evaluate the hscode_manager agent on the verified test products.

Each product in test-data/test_products.json is sent to the agent as one
request whose message lists the product's fields as key-value pairs
(product description: "...", brand: "...", ...). The first classification the
agent returns is scored against the product's declared HS code, and the run's
metrics are logged to MLflow. Settings come from .env (see .env.example);
results are written to results/.
"""

from mlflowfunctions import (
    mlflow_init,
    mlflow_log_data,
    mlflow_log_params,
    mlflow_log_metric,
)
import builtins
import collections
import datetime
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import dotenv
import pandas as pd
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

import hs_code_comparison
from hs_code_comparison import compare_hs_codes, load_customs_book

try:
    from tqdm import tqdm
except ImportError:  # optional: without it the per-product lines still print
    tqdm = None

dotenv.load_dotenv()
urllib3.disable_warnings(InsecureRequestWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_PRODUCTS_FILE = os.path.join(HERE, "test-data", "test_products.json")
RESULTS_DIR = os.path.join(HERE, "results")

# ── Settings (.env) ─────────────────────────────────────────────────────────
NUM_RUNS = int(os.getenv("NUM_RUNS", "1"))
experiment_name = os.getenv("EXPERIMENT_NAME", "hs-classifier-verified-products")
experiment_description = os.getenv("EXPERIMENT_DESCRIPTION", "")
run_name = os.getenv("RUN_NAME") or datetime.datetime.now().strftime("run-%Y-%m-%d-%H%M")
run_description = os.getenv("RUN_DESCRIPTION", "")
username_for_agent = os.getenv("USERNAME_FOR_AGENT", "dev-user")
USE_TOKEN_AUTH = os.getenv("USE_TOKEN_AUTH", "false").lower() == "true"

test_params = {
    "agent_url": os.getenv(
        "AGENT_URL",
        "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
    ),
    "agent_name": os.getenv("AGENT_NAME", "hscode_manager"),
    "threads_number": int(os.getenv("THREADS_NUMBER", "16")),
    "request_timeout_seconds": int(os.getenv("REQUEST_TIMEOUT_SECONDS", "600")),
    # Labels only: the server decides the models, prompt and web search. Record
    # here what the server ran with so runs can be told apart in MLflow.
    "model_used_for_candidates_generation": os.getenv("MODEL_USED_FOR_CANDIDATES_GENERATION", ""),
    "model_used_for_process": os.getenv("MODEL_USED_FOR_PROCESS", ""),
    "llm_direct_prompt": os.getenv("LLM_DIRECT_PROMPT", ""),
    "server_notes": os.getenv("SERVER_NOTES", ""),
}

# ── Service token authentication (client_credentials grant) ────────────────
if USE_TOKEN_AUTH:
    _KEYCLOAK_BASE = {
        "dev": "https://authentik.mdev.mehes.gov.il",
        "prod": "https://authentik.prod.mehes.gov.il",
    }.get(os.environ.get("CURA_AUTH_ENV", "dev"), "https://authentik.mdev.mehes.gov.il")
    _REALM = os.environ.get("KEYCLOAK_REALM", "entic")
    _TOKEN_ENDPOINT = f"{_KEYCLOAK_BASE}/realms/{_REALM}/protocol/openid-connect/token"

    _svc_token = None
    _svc_token_expires = 0.0
    _svc_token_lock = threading.Lock()

    def get_service_token() -> str:
        """Return a cached client_credentials access token, refreshing as needed."""
        global _svc_token, _svc_token_expires
        with _svc_token_lock:
            if _svc_token and time.time() < _svc_token_expires - 30:
                return _svc_token
            r = requests.post(
                _TOKEN_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": os.environ["KEYCLOAK_CLIENT_ID"],
                    "client_secret": os.environ["KEYCLOAK_CLIENT_SECRET"],
                },
                verify=False,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            _svc_token = data["access_token"]
            _svc_token_expires = time.time() + data.get("expires_in", 300)
            return _svc_token


# ── Request ─────────────────────────────────────────────────────────────────
# Product fields sent to the agent, in message order, with the key each is
# written under. Only what describes the product: the invoice HS code would
# give the expected answer away.
MESSAGE_FIELDS = (
    ("description", "product description"),
    ("brand", "brand"),
    ("model", "model"),
    ("general_product", "general product"),
    ("purpose", "purpose"),
)


def build_message(product):
    """'product description: "...", brand: "...", ...' with only the fields the
    product has."""
    parts = []
    for field, key in MESSAGE_FIELDS:
        value = product.get(field)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        value = str(value).strip()
        if value:
            parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return ", ".join(parts)


_debug_lock = threading.Lock()


def query_agent(message):
    payload = {
        "agent_name": test_params["agent_name"],
        "input_data": {"message": message},
        "mode": "background",
    }
    kwargs = dict(verify=False, timeout=test_params["request_timeout_seconds"])
    if USE_TOKEN_AUTH:
        kwargs["headers"] = {"Authorization": f"Bearer {get_service_token()}"}
    else:
        payload["username"] = username_for_agent
    response = requests.post(test_params["agent_url"], json=payload, **kwargs)
    with _debug_lock, open(os.path.join(RESULTS_DIR, "run-debug.jsonl"), "a", encoding="utf-8") as f:
        f.write(response.text + "\n")
    response.raise_for_status()
    return response.json()


# ── Scoring ─────────────────────────────────────────────────────────────────
# Server routes (metadata.classification_source), grouped by who produced the
# candidates. The server's own candidates_source is derived from the route name
# ("milvus" iff the route starts with "milvus"), which labels the hybrid route
# (no confident Milvus match, LLM proposes) as milvus and external_candidates
# (confident Milvus candidates) as llm - so it is not used here.
# Milvus decided alone, no LLM involved
MILVUS_DECIDED_ROUTES = {"milvus_single_leaf", "milvus_synthetic_leaf"}
# confident Milvus candidates, the LLM only evaluates them (proposes nothing)
MILVUS_CANDIDATE_ROUTES = {
    "external_candidates",
    "milvus_candidates",
    "milvus_synthetic_candidate",
    "milvus_multiple_leaves",
}
# no confident Milvus match: the LLM proposes, plus up to 3 weak Milvus hints
MILVUS_HINT_ROUTES = {"milvus_and_llm_hybrid"}


def candidates_source_for(route):
    if not route:
        return None
    if route in MILVUS_DECIDED_ROUTES or route in MILVUS_CANDIDATE_ROUTES:
        return "milvus"
    if route in MILVUS_HINT_ROUTES:
        return "llm_with_milvus_hints"
    return "llm"


def get_correct_until_level(predicted_code, actual_code):
    correct_until = 0
    for i in range(2, 11, 2):
        if predicted_code[:i] == actual_code[:i]:
            correct_until = i
        else:
            break
    return correct_until


def remove_even_trailing_zeros(code):
    zeros_removed = code.rstrip("0")
    return zeros_removed + "0" if len(zeros_removed) % 2 != 0 else zeros_removed


def first_classification(results):
    """The first entry of result.classification_results (the product sent)."""
    result = results.get("result") or {}
    if not isinstance(result, dict):
        return {}
    return (result.get("classification_results") or [{}])[0] or {}


def _code_covers(candidate, expected):
    """A candidate covers the correct code when either is a prefix of the other
    (expected codes aren't always padded to 10 digits)."""
    return (
        bool(candidate)
        and bool(expected)
        and (expected.startswith(candidate) or candidate.startswith(expected))
    )


def correct_in_candidates(codes, expected):
    """True/False if any candidate covers expected; None when the generator
    produced no candidates."""
    if not codes:
        return None
    return any(_code_covers(c, expected) for c in codes)


def candidate_fields(results, expected_code):
    """Routing and candidate-recall fields, computed for every row (success or
    failure) since candidate generation runs regardless of the final outcome.

    ``llm_candidate_stage_ran`` is False when the route never asks the LLM to
    propose candidates (Milvus decided alone, or handed confident candidates
    straight to evaluation) — those rows are excluded from LLM candidate recall.
    """
    entry = first_classification(results)
    summary = entry.get("classification_summary") or {}
    meta = (entry.get("classification_json") or {}).get("metadata") or {}
    # metadata is the fuller source; summary.llm_suggested_codes is often empty
    milvus = [
        c.get("code")
        for c in (meta.get("milvus_suggested_codes") or [])
        if isinstance(c, dict) and c.get("code")
    ]
    llm = list(meta.get("llm_suggested_codes") or summary.get("llm_suggested_codes") or [])
    route = summary.get("classification_source") or meta.get("classification_source")
    correct_in_milvus = correct_in_candidates(milvus, expected_code)
    correct_in_llm = correct_in_candidates(llm, expected_code)
    return {
        "route": route,
        "candidates_source": candidates_source_for(route),
        "classification_source": (
            ("milvus" if route in MILVUS_DECIDED_ROUTES else "llm") if route else None
        ),
        "correct_in_milvus_candidates": correct_in_milvus,
        "correct_in_llm_candidates": correct_in_llm,
        "correct_in_any_candidate": (correct_in_milvus is True) or (correct_in_llm is True),
        "llm_candidate_stage_ran": route not in MILVUS_DECIDED_ROUTES
        and route not in MILVUS_CANDIDATE_ROUTES,
    }


def rate_agent_result(product, results):
    """Score an agent response against product["expected_code"]."""
    expected_code = product["expected_code"]
    failed = {
        "description": product["description"],
        "did_server_responded": True,
        "success": False,
        "actual_code": expected_code,
        "full_result": json.dumps(results),
        **candidate_fields(results, expected_code),
        "any_leaf_full_match_incl_alternatives": None,
    }
    if not results.get("success"):
        print(f"Agent returned an unsuccessful result for {product['table_extraction_id']}")
        return failed

    entry = first_classification(results)
    summary = entry.get("classification_summary")
    if not summary or not summary.get("predicted_hs_code"):
        # NEEDS_CLARIFICATION with no code, or no product extracted
        return failed

    predicted_hs_code = summary["predicted_hs_code"]
    code_comparison = compare_hs_codes(predicted_hs_code, expected_code)

    # Also count a full leaf match among the alternatives
    any_leaf_full_match_incl_alt = code_comparison["any_leaf_full_match"]
    if not any_leaf_full_match_incl_alt:
        class_result = (entry.get("classification_json") or {}).get("classification_result") or {}
        for alt in class_result.get("alternative_matches") or []:
            if alt.get("hs_code") and compare_hs_codes(alt["hs_code"], expected_code)["any_leaf_full_match"]:
                any_leaf_full_match_incl_alt = True
                break

    token_usage = results.get("token_usage") or {}
    return {
        "description": product["description"],
        "did_server_responded": True,
        "success": True,
        "predicted_code": predicted_hs_code,
        "actual_code": expected_code,
        "did_found_leaf": summary["is_leaf"],
        "status": entry.get("classification_status"),
        "length_of_predicted_code": (
            10 if summary["is_leaf"] else len(remove_even_trailing_zeros(predicted_hs_code))
        ),
        "are_given_digits_correct": code_comparison.get("is_correct_hierarchy", False),
        "correct_until": get_correct_until_level(predicted_hs_code, expected_code),
        **candidate_fields(results, expected_code),
        "server_run_time_minutes": summary["total_runtime_minutes"],
        "llm_calls_count": summary["total_llm_calls"],
        "total_input_tokens": token_usage.get("total_input_tokens", 0),
        "total_output_tokens": token_usage.get("total_output_tokens", 0),
        "full_result": json.dumps(results),
        "mas_knia_mismatch": code_comparison["mas_knia_mismatch"],
        "general_customs_mismatch": code_comparison["general_customs_mismatch"],
        "requirements_mismatch": code_comparison["requirements_mismatch"],
        "any_leaf_full_match": code_comparison["any_leaf_full_match"],
        "any_leaf_full_match_incl_alternatives": any_leaf_full_match_incl_alt,
    }


def identify_product(product):
    message = build_message(product)
    try:
        results = query_agent(message)
    except Exception as e:
        print(f"Error querying agent for {product['table_extraction_id']}: {e}")
        # Server never answered: no candidates at all -> counts as a miss.
        return {
            "table_extraction_id": product["table_extraction_id"],
            "message": message,
            "description": product["description"],
            "did_server_responded": False,
            "success": False,
            "actual_code": product["expected_code"],
            "correct_in_milvus_candidates": None,
            "correct_in_llm_candidates": None,
            "correct_in_any_candidate": False,
            "llm_candidate_stage_ran": True,
            "any_leaf_full_match_incl_alternatives": None,
        }
    return {
        "table_extraction_id": product["table_extraction_id"],
        "message": message,
        **rate_agent_result(product, results),
    }


# ── Metrics ─────────────────────────────────────────────────────────────────
def _build_comparison_metrics(success_df):
    """Tax and legal-requirements comparison over the success subset, for rows
    with non-null comparison values."""
    cols = [
        "mas_knia_mismatch",
        "general_customs_mismatch",
        "requirements_mismatch",
        "any_leaf_full_match",
        "any_leaf_full_match_incl_alternatives",
    ]
    subset = success_df[success_df[cols].notna().all(axis=1)]
    rate = lambda col: subset[col].astype(float).mean() if len(subset) else float("nan")
    return {
        "34_mas_knia_mismatch_rate": rate("mas_knia_mismatch"),
        "35_general_customs_mismatch_rate": rate("general_customs_mismatch"),
        "36_requirements_mismatch_rate": rate("requirements_mismatch"),
        "37_no_tax_or_requirements_mismatch_rate": rate("any_leaf_full_match"),
        "37b_no_tax_or_req_mismatch_incl_alternatives_rate": rate(
            "any_leaf_full_match_incl_alternatives"
        ),
    }


def compute_metrics(results_df):
    # success = a final HS code was produced (NEEDS_CLARIFICATION rows that
    # carry a code count as success). Correctness / distribution metrics are
    # computed over this success subset; candidate recall over all rows.
    for col in ("success", "length_of_predicted_code", "candidates_source", "classification_source"):
        if col not in results_df.columns:
            results_df[col] = None
    results_df["success"] = results_df["success"] == True
    success_df = results_df[results_df["success"]]
    n_total = len(results_df)
    n_success = len(success_df)

    def correct_rate(rows):
        return rows["are_given_digits_correct"].astype(float).mean() if len(rows) else float("nan")

    metrics = {
        "01_total_tests_count": n_total,
        "02_success_rate": n_success / n_total,
        "03_failure_rate": (n_total - n_success) / n_total,
        "25_failure_count": n_total - n_success,
    }
    # length-distribution rates over ALL products; correctness within each
    # bucket over the success subset
    for n, digits in enumerate((2, 4, 6, 8, 10)):
        bucket = success_df[success_df["length_of_predicted_code"] == digits]
        metrics[f"{4 + 3 * n:02d}_response_with_{digits}_digits_rate"] = (
            results_df["length_of_predicted_code"] == digits
        ).mean()
        metrics[f"{5 + 3 * n:02d}_correct_when_return_{digits}_rate"] = correct_rate(bucket)
        metrics[f"{6 + 3 * n:02d}_average_correct_digits_when_return_{digits}"] = (
            bucket["correct_until"].mean() if len(bucket) else float("nan")
        )
    cand, cls = results_df["candidates_source"], results_df["classification_source"]
    s_cand, s_cls = success_df["candidates_source"], success_df["classification_source"]
    metrics.update({
        # routing over ALL products
        "19_candidates_from_milvus_rate": (cand == "milvus").mean(),
        "19b_candidates_from_llm_with_milvus_hints_rate": (cand == "llm_with_milvus_hints").mean(),
        "20_candidate_from_llm_rate": (cand == "llm").mean(),
        "21_classification_from_milvus_rate": (cls == "milvus").mean(),
        "22_classification_from_llm_rate": (cls == "llm").mean(),
        "23_candidate_from_milvus_and_classification_from_llm_rate": (
            (cand == "milvus") & (cls == "llm")
        ).mean(),
        "27_correct_response_rate_when_classification_from_milvus": correct_rate(
            success_df[s_cls == "milvus"]
        ),
        "28_correct_response_rate_when_classification_from_llm": correct_rate(
            success_df[s_cls == "llm"]
        ),
        "29_correct_response_rate_when_candidates_from_milvus_and_classification_from_llm": correct_rate(
            success_df[(s_cand == "milvus") & (s_cls == "llm")]
        ),
        "29b_correct_response_rate_when_candidates_from_llm_with_milvus_hints": correct_rate(
            success_df[s_cand == "llm_with_milvus_hints"]
        ),
        "29c_correct_response_rate_when_candidates_from_llm_only": correct_rate(
            success_df[s_cand == "llm"]
        ),
        "30_average_server_run_time_minutes_for_successful_responses": success_df[
            "server_run_time_minutes"
        ].astype(float).mean(),
        "31_average_llm_calls_count_for_successful_responses": success_df[
            "llm_calls_count"
        ].astype(float).mean(),
        "32_average_total_input_tokens_for_successful_responses": success_df[
            "total_input_tokens"
        ].astype(float).mean(),
        "33_average_total_output_tokens_for_successful_responses": success_df[
            "total_output_tokens"
        ].astype(float).mean(),
        "39_correct_response_rate_overall": correct_rate(success_df),
        # candidate recall over the WHOLE dataset (failed / no-candidate rows
        # are misses)
        "38_correct_in_any_candidate_rate": (results_df["correct_in_any_candidate"] == True).mean(),
        "40_correct_in_milvus_candidates_rate": (
            results_df["correct_in_milvus_candidates"] == True
        ).mean(),
        # only rows where the LLM was asked to propose candidates
        "41_correct_in_llm_candidates_rate": (
            results_df[results_df["llm_candidate_stage_ran"] == True]["correct_in_llm_candidates"]
            == True
        ).mean(),
        **_build_comparison_metrics(success_df),
    })
    return metrics


# ── Progress ────────────────────────────────────────────────────────────────
class Progress:
    """One progress bar for all runs, pinned to the last line of the terminal.

    While it is active, print() writes above the bar (through tqdm.write), so
    log lines scroll without breaking it. The bar is off when tqdm is missing
    or stdout is not a terminal; the per-product lines are printed either way.
    """

    def __init__(self, total):
        self.lock = threading.Lock()
        self.counts = collections.Counter()
        self.bar = None
        if tqdm is not None:
            self.bar = tqdm(total=total, unit="product", dynamic_ncols=True, disable=None)
            if self.bar.disable:
                self.bar = None

    def __enter__(self):
        if self.bar:
            self._print = builtins.print
            builtins.print = self._write
        return self

    def __exit__(self, *exc):
        if self.bar:
            builtins.print = self._print
            self.bar.close()

    def _write(self, *args, sep=" ", end="\n", file=None, flush=False):
        if file not in (None, sys.stdout):
            return self._print(*args, sep=sep, end=end, file=file, flush=flush)
        tqdm.write(sep.join(str(a) for a in args), end=end)

    @staticmethod
    def _outcome(row):
        if not row.get("did_server_responded"):
            return "server error"
        if not row.get("success"):
            return "no code"
        return "correct" if row.get("are_given_digits_correct") else "wrong"

    def product_done(self, future, run_index):
        # Runs in the worker thread when a product finishes. A product whose
        # scoring raised still advances the bar; collect_run re-raises it.
        if future.exception() is not None:
            outcome = "crashed"
            print(f"run {run_index} | scoring crashed: {future.exception()!r}")
        else:
            row = future.result()
            outcome = self._outcome(row)
            print(f"run {run_index} | {row['table_extraction_id']} | {outcome:12} | "
                  f"expected {row.get('actual_code')} agent {row.get('predicted_code') or '-'}")
        with self.lock:
            self.counts[outcome] += 1
            if self.bar:
                self.bar.set_postfix({k: n for k, n in self.counts.items() if n}, refresh=False)
                self.bar.update(1)


# ── Run ─────────────────────────────────────────────────────────────────────
def submit_run(test_products, run_index, executor, progress):
    print(f"Run {run_index}/{NUM_RUNS}: submitting agent queries for all products...")
    futures = [executor.submit(identify_product, product) for product in test_products]
    for f in futures:
        f.add_done_callback(lambda f, r=run_index: progress.product_done(f, r))
    return futures


def collect_run(submitted, run_index):
    result_list = [f.result() for f in submitted]
    results_df = pd.DataFrame(result_list)
    path = os.path.join(RESULTS_DIR, f"classification-results-run{run_index}.csv")
    results_df.to_csv(path)
    print(f"Results saved to {path}")
    return results_df


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(
        f"Testing {test_params['agent_name']} at {test_params['agent_url']} with "
        f"{test_params['threads_number']} threads, {test_params['request_timeout_seconds']}s "
        f"timeout per request, {NUM_RUNS} run(s)."
    )

    mlflow_init(
        experiment_name=experiment_name,
        experiment_description=experiment_description,
        run_name=run_name,
        run_description=run_description,
        files_lst=[__file__, hs_code_comparison.__file__],
    )

    with open(TEST_PRODUCTS_FILE, encoding="utf-8") as f:
        products_df = pd.DataFrame(json.load(f))
    products_df["table_extraction_id"] = products_df["table_extraction_id"].astype(str)
    products_df = products_df.rename(columns={"hs_code": "expected_code"})
    products_df["message"] = products_df.apply(build_message, axis=1)

    mlflow_log_data(products_df, "test-products")
    mlflow_log_params({**test_params, "products_count": len(products_df), "num_runs": NUM_RUNS})

    print("Loading customs book index...")
    load_customs_book()

    test_products = products_df.drop(columns=["message"]).to_dict(orient="records")
    per_run_metrics = []
    with Progress(total=NUM_RUNS * len(test_products)) as progress, ThreadPoolExecutor(
        max_workers=test_params["threads_number"]
    ) as executor:
        # Every run is submitted up front so all runs share one pool.
        submitted = [
            submit_run(test_products, run_index, executor, progress)
            for run_index in range(1, NUM_RUNS + 1)
        ]
        for run_index, run_submitted in zip(range(1, NUM_RUNS + 1), submitted):
            results_df = collect_run(run_submitted, run_index)
            mlflow_log_data(results_df, f"classification-results-run{run_index}")
            per_run_metrics.append(compute_metrics(results_df))

    per_run_df = pd.DataFrame(per_run_metrics, index=[f"run{i}" for i in range(1, NUM_RUNS + 1)])
    per_run_df.to_csv(os.path.join(RESULTS_DIR, "metrics-per-run.csv"))
    mlflow_log_data(per_run_df.reset_index(names="run"), "metrics-per-run")

    avg_metrics = per_run_df.mean(numeric_only=True).to_dict()
    pd.DataFrame([avg_metrics]).to_csv(os.path.join(RESULTS_DIR, "metrics.csv"), index=False)
    mlflow_log_metric(avg_metrics)

    print(f"\nAveraged metrics over {NUM_RUNS} run(s):")
    for key, value in avg_metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
