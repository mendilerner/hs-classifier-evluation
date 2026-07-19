"""Build the classifier input dataset from the raw verified-classification dump.

verified-classification.csv is a headerless DB export; the columns below are the
only ones we consume. Fields left empty in the dump stay empty here and are sent
to the agent as JSON null.
"""

import pandas as pd

SOURCE = "./verified-classification.csv"
TARGET = "./verified-classification-input.csv"

# Column positions in the headerless dump.
COLUMNS = {
    6: "description",
    19: "general_product",
    20: "purpose",
    17: "brand",
    18: "model",
    22: "expected_code",  # cols 22/24/25 are identical across every row
}


def main():
    raw = pd.read_csv(SOURCE, header=None, dtype=str, encoding="utf-8-sig")
    data = raw[list(COLUMNS)].rename(columns=COLUMNS)
    data = data[
        ["description", "general_product", "purpose", "brand", "model", "expected_code"]
    ]
    data.to_csv(TARGET)
    print(f"Wrote {len(data)} products to {TARGET}")
    print(data.notna().sum().to_string())


if __name__ == "__main__":
    main()
