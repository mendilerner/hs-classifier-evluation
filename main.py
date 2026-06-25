from mlflowfunctions import (
    mlflow_init,
    mlflow_log_data,
    mlflow_log_params,
    mlflow_log_metric,
)
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


username_for_agent = os.getenv("USERNAME_FOR_AGENT", "dev-user")
experiment_name = os.environ["EXPERIMENT_NAME"]
experiment_description = os.getenv("EXPERIMENT_DESCRIPTION", "")
run_name = os.environ["RUN_NAME"]
run_description = os.getenv("RUN_DESCRIPTION", "")


test_params = {
    "agent_url": os.getenv(
        "AGENT_URL",
        "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run",
    ),
    "agent_name": os.getenv("AGENT_NAME", "hscode_manager"),
    "threads_number": int(os.getenv("THREADS_NUMBER", "16")),
    "request_timeout_seconds": int(os.getenv("REQUEST_TIMEOUT_SECONDS", "600")),
    "model_used_for_candidates_generation": os.environ[
        "MODEL_USED_FOR_CANDIDATES_GENERATION"
    ],
    "model_used_for_process": os.environ["MODEL_USED_FOR_PROCESS"],
    "max_token_on_prem": os.environ["MAX_TOKEN_ON_PREM"],
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
    zeros_removed = code.rstrip("0")
    return zeros_removed + "0" if len(zeros_removed) % 2 != 0 else zeros_removed


def query_agent(product_description):
    print("sending request. product description:", product_description)
    response = requests.post(
        test_params["agent_url"],
        json={
            "agent_name": test_params["agent_name"],
            "input_data": {"message": product_description},
            "username": username_for_agent,
            "mode": "background",
        },
        verify=False,
        timeout=test_params["request_timeout_seconds"],
    )
    print(
        "product:", product_description, "response.status_code:", response.status_code
    )
    with open("run-debug.jsonl", "a") as f:
        f.write(response.text + "\n")
    response.raise_for_status()
    result = response.json()
    return result


def extract_classification(results):
    """Return (classification_summary, status) from either the hscode_manager
    response shape (result.classification_results[]) or the direct
    hsCode_classifier shape (flat result.classification_summary).

    Returns (None, None) when the manager extracted no products.
    """
    result = results["result"]
    if "classification_results" in result:
        classification_results = result.get("classification_results") or []
        if not classification_results:
            return None, None
        first = classification_results[0]
        return first["classification_summary"], first["classification_status"]
    return result["classification_summary"], result["status"]


def identify_product(product):
    description = product["description"]
    try:
        results = query_agent(description)
    except Exception as e:
        print("Error querying agent for product:", product, "Error:", str(e))
        return {
            "description": description,
            "did_server_responded": False,
            "actual_code": product["expected_code"],
        }
    if results["success"] == False:
        print(
            "Agent returned unsuccessful result for product:",
            product,
            "Result:",
            results,
        )
        return {
            "description": description,
            "did_server_responded": True,
            "success": False,
            "actual_code": product["expected_code"],
            "full_result": results,
        }

    summary, status = extract_classification(results)
    if summary is None:
        print(
            "Manager returned no classification results for product:",
            product,
            "Result:",
            results,
        )
        return {
            "description": description,
            "did_server_responded": True,
            "success": False,
            "actual_code": product["expected_code"],
            "full_result": json.dumps(results),
        }

    predicted_hs_code = summary["predicted_hs_code"]

    code_comparison = compare_hs_codes(predicted_hs_code, product["expected_code"])

    return {
        "description": description,
        "did_server_responded": True,
        "success": True,
        "predicted_code": predicted_hs_code,
        "actual_code": product["expected_code"],
        "did_found_leaf": summary["is_leaf"],
        "status": status,
        "length_of_predicted_code": (
            len(remove_even_trailing_zeros(predicted_hs_code))
            if not summary["is_leaf"]
            else 10
        ),
        "are_given_digits_correct": predicted_hs_code[
            : len(remove_even_trailing_zeros(predicted_hs_code))
        ]
        == product["expected_code"][
            : len(remove_even_trailing_zeros(predicted_hs_code))
        ],
        "correct_until": get_correct_until_level(
            predicted_hs_code, product["expected_code"]
        ),
        "candidates_source": (
            "milvus"
            if summary["candidates_source"] == "milvus"
            else "llm"
        ),
        "classification_source": (
            "milvus"
            if summary["classification_source"] == "milvus_single_leaf"
            else "llm"
        ),
        "was_correct_code_in_candidates": (
            any(
                product["expected_code"].startswith(code)
                for code in summary["llm_suggested_codes"]
            )
            if summary["candidates_source"] == "llm_direct"
            else None
        ),
        "server_run_time_minutes": summary["total_runtime_minutes"],
        "llm_calls_count": summary["total_llm_calls"],
        "total_input_tokens": (
            results["token_usage"]["total_input_tokens"]
            if results["token_usage"]
            else 0
        ),
        "total_output_tokens": (
            results["token_usage"]["total_output_tokens"]
            if results["token_usage"]
            else 0
        ),
        "full_result": json.dumps(results),
        "mas_knia_mismatch": code_comparison["mas_knia_mismatch"],
        "general_customs_mismatch": code_comparison["general_customs_mismatch"],
        "requirements_mismatch": code_comparison["requirements_mismatch"],
        "any_leaf_full_match": code_comparison["any_leaf_full_match"],
    }


def _build_comparison_metrics(results_df, okay_responses_filter):
    """Build tax and legal-requirements comparison metrics from results_df.

    Only rows that passed okay_responses_filter AND have non-null comparison
    values are included in each rate calculation.
    """
    comparison_ok = (
        okay_responses_filter
        & results_df["mas_knia_mismatch"].notna()
        & results_df["general_customs_mismatch"].notna()
        & results_df["requirements_mismatch"].notna()
        & results_df["any_leaf_full_match"].notna()
    )
    subset = results_df[comparison_ok]
    if len(subset) == 0:
        return {
            "34_mas_knia_mismatch_rate": float("nan"),
            "35_general_customs_mismatch_rate": float("nan"),
            "36_requirements_mismatch_rate": float("nan"),
            "37_no_tax_or_requirements_mismatch_rate": float("nan"),
        }
    return {
        "34_mas_knia_mismatch_rate": subset["mas_knia_mismatch"].astype(float).mean(),
        "35_general_customs_mismatch_rate": subset["general_customs_mismatch"]
        .astype(float)
        .mean(),
        "36_requirements_mismatch_rate": subset["requirements_mismatch"]
        .astype(float)
        .mean(),
        "37_no_tax_or_requirements_mismatch_rate": subset["any_leaf_full_match"]
        .astype(float)
        .mean(),
    }


def main():
    print(
        "Starting classifier test with url:",
        test_params["agent_url"],
        "using agent:",
        test_params["agent_name"],
        "with",
        test_params["threads_number"],
        "threads and",
        test_params["request_timeout_seconds"],
        "seconds timeout per request.",
    )

    mlflow_init(
        experiment_name=experiment_name,
        experiment_description=experiment_description,
        run_name=run_name,
        run_description=run_description,
        files_lst=[__file__, hs_code_comparison.__file__],
    )

    with open("./classified-data-input.csv") as f:
        test_data = pd.read_csv(f, index_col="Unnamed: 0", dtype=str)

    mlflow_log_data(test_data, "classified-data")

    mlflow_log_params(test_params)

    print("Loading customs book index...")
    load_customs_book()

    with ThreadPoolExecutor(max_workers=test_params["threads_number"]) as p:
        result_set = p.map(identify_product, test_data.to_dict(orient="records"))

    results_df = pd.DataFrame(result_set)

    mlflow_log_data(results_df, "classification-results")

    okay_responses_filter = (
        (results_df["did_server_responded"] == True)
        & (results_df["success"] == True)
        & (results_df["status"] != "ERROR")
    )
    len_okay_responses = len(results_df[okay_responses_filter])

    metrics = {
        "01_total_tests_count": len(results_df),
        "02_okay_responses_rate": len_okay_responses / len(results_df),
        "03_error_rate": (len(results_df) - len_okay_responses) / len(results_df),
        "04_response_with_2_digits_rate": (
            results_df["length_of_predicted_code"] == 2
        ).mean(),
        "05_correct_when_return_2_rate": results_df[
            (results_df["length_of_predicted_code"] == 2)
        ]["are_given_digits_correct"].mean(),
        "06_average_correct_digits_when_return_2": results_df[
            results_df["length_of_predicted_code"] == 2
        ]["correct_until"].mean(),
        "07_response_with_4_digits_rate": (
            results_df["length_of_predicted_code"] == 4
        ).mean(),
        "08_correct_when_return_4_rate": results_df[
            (results_df["length_of_predicted_code"] == 4)
        ]["are_given_digits_correct"].mean(),
        "09_average_correct_digits_when_return_4": results_df[
            results_df["length_of_predicted_code"] == 4
        ]["correct_until"].mean(),
        "10_response_with_6_digits_rate": (
            results_df["length_of_predicted_code"] == 6
        ).mean(),
        "11_correct_when_return_6_rate": results_df[
            results_df["length_of_predicted_code"] == 6
        ]["are_given_digits_correct"].mean(),
        "12_average_correct_digits_when_return_6": results_df[
            results_df["length_of_predicted_code"] == 6
        ]["correct_until"].mean(),
        "13_response_with_8_digits_rate": (
            results_df["length_of_predicted_code"] == 8
        ).mean(),
        "14_correct_when_return_8_rate": results_df[
            results_df["length_of_predicted_code"] == 8
        ]["are_given_digits_correct"].mean(),
        "15_average_correct_digits_when_return_8": results_df[
            results_df["length_of_predicted_code"] == 8
        ]["correct_until"].mean(),
        "16_response_with_10_digits_rate": (
            results_df["length_of_predicted_code"] == 10
        ).mean(),
        "17_correct_when_return_10_rate": results_df[
            results_df["length_of_predicted_code"] == 10
        ]["are_given_digits_correct"].mean(),
        "18_average_correct_digits_when_return_10": results_df[
            results_df["length_of_predicted_code"] == 10
        ]["correct_until"].mean(),
        "19_candidates_from_milvus_rate": (
            results_df["candidates_source"] == "milvus"
        ).mean(),
        "20_candidate_from_llm_rate": (results_df["candidates_source"] == "llm").mean(),
        "21_classification_from_milvus_rate": (
            results_df["classification_source"] == "milvus"
        ).mean(),
        "22_classification_from_llm_rate": (
            results_df["classification_source"] == "llm"
        ).mean(),
        "23_candidate_from_milvus_and_classification_from_llm_rate": (
            (results_df["candidates_source"] == "milvus")
            & (results_df["classification_source"] == "llm")
        ).mean(),
        "24_no_response_from_server_count": (
            results_df["did_server_responded"] == False
        ).sum(),
        "25_response_with_success_false_count": (results_df["success"] == False).sum(),
        "26_response_with_error_status_count": (results_df["status"] == "ERROR").sum(),
        "27_correct_response_rate_when_classification_from_milvus": results_df[
            results_df["classification_source"] == "milvus"
        ]["are_given_digits_correct"].mean(),
        "28_correct_response_rate_when_classification_from_llm": results_df[
            results_df["classification_source"] == "llm"
        ]["are_given_digits_correct"].mean(),
        "29_correct_response_rate_when_candidates_from_milvus_and_classification_from_llm": results_df[
            (results_df["candidates_source"] == "milvus")
            & (results_df["classification_source"] == "llm")
        ][
            "are_given_digits_correct"
        ].mean(),
        "30_average_server_run_time_minutes_for_successful_responses": results_df[
            okay_responses_filter
        ]["server_run_time_minutes"].mean(),
        "31_average_llm_calls_count_for_successful_responses": results_df[
            okay_responses_filter
        ]["llm_calls_count"].mean(),
        "32_average_total_input_tokens_for_successful_responses": results_df[
            okay_responses_filter
        ]["total_input_tokens"].mean(),
        "33_average_total_output_tokens_for_successful_responses": results_df[
            okay_responses_filter
        ]["total_output_tokens"].mean(),
        "38_was_correct_code_in_candidates_rate_when_candidates_from_llm_direct": results_df[
            results_df["was_correct_code_in_candidates"].notna()
        ][
            "was_correct_code_in_candidates"
        ].astype(
            float
        ).mean(),
        "39_correct_response_rate_overall": results_df[
            "are_given_digits_correct"
        ].mean(),
        **_build_comparison_metrics(results_df, okay_responses_filter),
    }

    mlflow_log_metric(metrics)

    print(results_df)


if __name__ == "__main__":
    main()
