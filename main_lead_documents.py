"""Evaluate the hscode_manager agent on whole lead documents.

Each lead document title (new-test-data/te_hs_lead_titles.txt) is sent to the
agent as one request. The agent extracts the invoice lines and classifies each
one; every classified line is matched to its expected HS code by
table_extraction_id (new-test-data/te_hs_codes.json) and rated exactly like
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
    "LEAD_DOC_EXPERIMENT_NAME", "hs-classifier-lead-documents"
)
experiment_description = main.experiment_description
run_name = main.run_name
run_description = main.run_description

LEAD_TITLES_FILE = "./new-test-data/te_hs_lead_titles.txt"
EXPECTED_CODES_FILE = "./new-test-data/te_hs_codes.json"
RESULTS_JSON = "lead-doc-agent-results.json"


def query_agent_with_lead_document(lead_document_title):
    print("sending request. lead document title:", lead_document_title)
    payload = {
        "agent_name": test_params["agent_name"],
        "input_data": {"lead_document_title": lead_document_title},
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
    print(
        "lead document:",
        lead_document_title,
        "response.status_code:",
        response.status_code,
    )
    with open("lead-doc-run-debug.jsonl", "a") as f:
        f.write(response.text + "\n")
    response.raise_for_status()
    return response.json()


def _entry_table_extraction_id(result, index, entry):
    """table_extraction_id of a classification_results entry: from the product
    metadata, falling back to the (index-aligned) background response list."""
    teid = ((entry.get("product") or {}).get("metadata") or {}).get(
        "table_extraction_id"
    )
    if teid is None:
        response = result.get("response")
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except ValueError:
                response = None
        extracted = (response or {}).get("products_extracted_from_invoice") or []
        if index < len(extracted):
            teid = extracted[index].get("table_extraction_id")
    return None if teid is None else str(teid)


def split_document_results(results):
    """Split a whole-document response into one single-product response per
    classified line, keyed by table_extraction_id, in the shape
    main.rate_agent_result expects. Document-level token usage is spread
    evenly across the document's products."""
    result = results.get("result") or {}
    if not isinstance(result, dict):
        return {}
    entries = result.get("classification_results") or []
    token_usage = results.get("token_usage")
    if token_usage and entries:
        token_usage = {
            "total_input_tokens": (token_usage.get("total_input_tokens") or 0)
            / len(entries),
            "total_output_tokens": (token_usage.get("total_output_tokens") or 0)
            / len(entries),
        }
    per_product = {}
    for index, entry in enumerate(entries):
        teid = _entry_table_extraction_id(result, index, entry)
        if teid is None:
            continue
        per_product[teid] = {
            "success": results.get("success"),
            "result": {"classification_results": [entry]},
            "token_usage": token_usage,
        }
    return per_product


def _failed_row(product, did_server_responded):
    return {
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


def process_lead_document(lead_document_title):
    """Query the agent for one lead document. Returns
    {"lead_document_title", "did_server_responded", "success", "per_product"}."""
    try:
        results = query_agent_with_lead_document(lead_document_title)
    except Exception as e:
        print("Error querying agent for lead document:", lead_document_title, e)
        return {
            "lead_document_title": lead_document_title,
            "did_server_responded": False,
            "per_product": {},
        }
    return {
        "lead_document_title": lead_document_title,
        "did_server_responded": True,
        "success": results.get("success"),
        "per_product": split_document_results(results),
    }


def rate_documents(document_results, expected_df):
    """Rate every expected line. A line is matched to its document's response
    by table_extraction_id; expected lines no document returned are failures."""
    rows = []
    found = set()
    responded_any = any(d["did_server_responded"] for d in document_results)
    for doc in document_results:
        doc_title = doc["lead_document_title"]
        for teid, product_results in doc["per_product"].items():
            match = expected_df[expected_df["table_extraction_id"] == teid]
            if match.empty:
                print(
                    f"lead document {doc_title}: table_extraction_id {teid} "
                    "has no expected code, skipping"
                )
                continue
            if teid in found:
                continue
            found.add(teid)
            product = match.iloc[0].to_dict()
            entry = product_results["result"]["classification_results"][0]
            product["description"] = (entry.get("product") or {}).get(
                "description"
            ) or ""
            row = rate_agent_result(product, product_results)
            rows.append(
                {"lead_document_title": doc_title, "table_extraction_id": teid, **row}
            )

    failed_docs = [
        d["lead_document_title"]
        for d in document_results
        if not d["did_server_responded"] or not d.get("success")
    ]
    if failed_docs:
        print("Lead documents that failed:", failed_docs)

    for product in expected_df.to_dict(orient="records"):
        teid = product["table_extraction_id"]
        if teid in found:
            continue
        print(f"table_extraction_id {teid} was not returned by any lead document")
        rows.append(
            {
                "lead_document_title": None,
                "table_extraction_id": teid,
                **_failed_row({**product, "description": ""}, responded_any),
            }
        )
    return rows


def submit_run(lead_titles, run_index, executor):
    results_json = RESULTS_JSON.replace(".json", f"-run{run_index}.json")
    if os.path.exists(results_json):
        print(f"Loading existing results from {results_json}, skipping agent run...")
        with open(results_json) as f:
            return json.load(f)

    print(f"Run {run_index}/{NUM_RUNS}: submitting agent queries for all documents...")
    return [executor.submit(process_lead_document, title) for title in lead_titles]


def collect_run(submitted, run_index, expected_df):
    results_json = RESULTS_JSON.replace(".json", f"-run{run_index}.json")

    if submitted and isinstance(submitted[0], Future):
        result_list = rate_documents([f.result() for f in submitted], expected_df)
        with open(results_json, "w", encoding="utf-8") as f:
            json.dump(result_list, f, indent=2, default=lambda x: None)
        print(f"Agent results saved to {results_json}")
    else:
        result_list = submitted

    results_df = pd.DataFrame(result_list)
    results_df.to_csv(f"lead-doc-classification-results-run{run_index}.csv")
    return results_df


def main_lead_documents():
    print(
        "Starting lead-document classifier test with url:",
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

    with open(LEAD_TITLES_FILE) as f:
        lead_titles = [line.strip() for line in f if line.strip()]
    with open(EXPECTED_CODES_FILE) as f:
        expected_df = pd.DataFrame(json.load(f)).astype(str)
    expected_df = expected_df.rename(columns={"hs_code": "expected_code"})

    mlflow_log_data(
        pd.DataFrame({"lead_document_title": lead_titles}), "lead-document-titles"
    )
    mlflow_log_data(expected_df, "expected-codes")

    mlflow_log_params(
        {
            **test_params,
            "lead_documents_count": len(lead_titles),
            "expected_lines_count": len(expected_df),
        }
    )

    print("Loading customs book index...")
    load_customs_book()

    per_run_metrics = []
    with ThreadPoolExecutor(max_workers=test_params["threads_number"]) as executor:
        submitted = [
            submit_run(lead_titles, run_index, executor)
            for run_index in range(1, NUM_RUNS + 1)
        ]
        for run_index, run_submitted in zip(range(1, NUM_RUNS + 1), submitted):
            results_df = collect_run(run_submitted, run_index, expected_df)
            mlflow_log_data(
                results_df, f"lead-doc-classification-results-run{run_index}"
            )
            per_run_metrics.append(compute_metrics(results_df))

    per_run_df = pd.DataFrame(
        per_run_metrics, index=[f"run{i}" for i in range(1, NUM_RUNS + 1)]
    )
    per_run_df.to_csv("lead-doc-metrics-per-run.csv")
    mlflow_log_data(per_run_df.reset_index(names="run"), "metrics-per-run")

    avg_metrics = per_run_df.mean(numeric_only=True).to_dict()
    pd.DataFrame([avg_metrics]).to_csv("lead-doc-metrics.csv", index=False)

    mlflow_log_metric(avg_metrics)

    print(f"\nAveraged metrics over {NUM_RUNS} runs:")
    for key, value in avg_metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main_lead_documents()
