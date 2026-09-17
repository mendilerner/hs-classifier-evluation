"""Evaluate the hscode_manager agent on the verified products of the lead-document set.

Each product in new-test-data/test_products.json is sent to the agent as one
request whose message lists the product's available fields as key-value pairs
(product description: "...", brand: "...", ...). The first classification the
agent returns is rated against the product's declared HS code exactly like
main.py rates a single-product request. Metrics are logged to MLflow under a
separate experiment.
"""

from mlflowfunctions import (
    mlflow_init,
    mlflow_log_data,
    mlflow_log_params,
    mlflow_log_metric,
)
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, Future
import json
import os
import requests
import hs_code_comparison
from hs_code_comparison import load_customs_book

import main
from main import (
    test_params,
    username_for_agent,
    USE_TOKEN_AUTH,
    rate_agent_result,
    compute_metrics,
    NUM_RUNS,
)

experiment_name = os.getenv(
    "PRODUCTS_EXPERIMENT_NAME", "hs-classifier-verified-products"
)
experiment_description = main.experiment_description
run_name = main.run_name
run_description = main.run_description

TEST_PRODUCTS_FILE = "./new-test-data/test_products.json"
RESULTS_JSON = "product-agent-results.json"

# Product fields sent to the agent, in message order, with the key each is
# written under. Only what describes the product: the invoice HS code and any
# stored prediction would give the expected answer away.
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


def query_agent_with_message(message):
    print("sending request. message:", message)
    payload = {
        "agent_name": test_params["agent_name"],
        "input_data": {"message": message},
        "mode": "background",
    }
    kwargs = dict(
        json=payload, verify=False, timeout=test_params["request_timeout_seconds"]
    )
    if USE_TOKEN_AUTH:
        response = main.authed_request("POST", test_params["agent_url"], **kwargs)
    else:
        payload["username"] = username_for_agent
        response = requests.post(test_params["agent_url"], **kwargs)
    print("message:", message, "response.status_code:", response.status_code)
    with open("product-run-debug.jsonl", "a", encoding="utf-8") as f:
        f.write(response.text + "\n")
    response.raise_for_status()
    return response.json()


def _failed_row(product, message, did_server_responded):
    return {
        "table_extraction_id": product["table_extraction_id"],
        "message": message,
        "description": product["description"],
        "did_server_responded": did_server_responded,
        "success": False,
        "actual_code": product["expected_code"],
        "correct_in_milvus_candidates": None,
        "correct_in_llm_candidates": None,
        "correct_in_any_candidate": False,
        "llm_candidate_stage_ran": True,
        "any_leaf_full_match_incl_alternatives": None,
    }


def identify_product(product):
    message = build_message(product)
    try:
        results = query_agent_with_message(message)
    except Exception as e:
        print("Error querying agent for product:", product, "Error:", str(e))
        return _failed_row(product, message, did_server_responded=False)
    return {
        "table_extraction_id": product["table_extraction_id"],
        "message": message,
        **rate_agent_result(product, results),
    }


def submit_run(test_products, run_index, executor):
    results_json = RESULTS_JSON.replace(".json", f"-run{run_index}.json")
    if os.path.exists(results_json):
        print(f"Loading existing results from {results_json}, skipping agent run...")
        with open(results_json) as f:
            return json.load(f)

    print(f"Run {run_index}/{NUM_RUNS}: submitting agent queries for all products...")
    return [executor.submit(identify_product, product) for product in test_products]


def collect_run(submitted, run_index):
    results_json = RESULTS_JSON.replace(".json", f"-run{run_index}.json")

    if submitted and isinstance(submitted[0], Future):
        result_list = [f.result() for f in submitted]
        with open(results_json, "w", encoding="utf-8") as f:
            json.dump(result_list, f, indent=2, default=lambda x: None)
        print(f"Agent results saved to {results_json}")
    else:
        result_list = submitted

    results_df = pd.DataFrame(result_list)
    results_df.to_csv(f"product-classification-results-run{run_index}.csv")
    return results_df


def main_lead_documents():
    print(
        "Starting verified-products classifier test with url:",
        test_params["agent_url"],
        "using agent:",
        test_params["agent_name"],
        "with",
        test_params["threads_number"],
        "threads and",
        test_params["request_timeout_seconds"],
        "seconds timeout per request.",
    )
    print(f"Running the test {NUM_RUNS} times and averaging the metrics.")

    mlflow_init(
        experiment_name=experiment_name,
        experiment_description=experiment_description,
        run_name=run_name,
        run_description=run_description,
        files_lst=[
            __file__,
            main.__file__,
            hs_code_comparison.__file__,
            "evaluate_batch.yaml",
        ],
    )

    with open(TEST_PRODUCTS_FILE, encoding="utf-8") as f:
        products_df = pd.DataFrame(json.load(f))
    products_df["table_extraction_id"] = products_df["table_extraction_id"].astype(str)
    products_df = products_df.rename(columns={"hs_code": "expected_code"})
    products_df["message"] = products_df.apply(build_message, axis=1)

    mlflow_log_data(products_df, "test-products")

    mlflow_log_params({**test_params, "products_count": len(products_df)})

    print("Loading customs book index...")
    load_customs_book()

    test_products = products_df.drop(columns=["message"]).to_dict(orient="records")
    per_run_metrics = []
    with ThreadPoolExecutor(max_workers=test_params["threads_number"]) as executor:
        submitted = [
            submit_run(test_products, run_index, executor)
            for run_index in range(1, NUM_RUNS + 1)
        ]
        for run_index, run_submitted in zip(range(1, NUM_RUNS + 1), submitted):
            results_df = collect_run(run_submitted, run_index)
            mlflow_log_data(
                results_df, f"product-classification-results-run{run_index}"
            )
            per_run_metrics.append(compute_metrics(results_df))

    per_run_df = pd.DataFrame(
        per_run_metrics, index=[f"run{i}" for i in range(1, NUM_RUNS + 1)]
    )
    per_run_df.to_csv("product-metrics-per-run.csv")
    mlflow_log_data(per_run_df.reset_index(names="run"), "metrics-per-run")

    avg_metrics = per_run_df.mean(numeric_only=True).to_dict()
    pd.DataFrame([avg_metrics]).to_csv("product-metrics.csv", index=False)

    mlflow_log_metric(avg_metrics)

    print(f"\nAveraged metrics over {NUM_RUNS} runs:")
    for key, value in avg_metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main_lead_documents()
