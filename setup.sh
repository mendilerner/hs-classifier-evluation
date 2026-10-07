#!/usr/bin/env bash
# One-time setup: creates .venv, installs everything, and creates .env.
# Usage: ./setup.sh   (asks for the Azure DevOps feed token, or set FEED_TOKEN)
set -euo pipefail
cd "$(dirname "$0")"

NEXUS=(-i http://nexus.mehes.gov.il:8081/repository/python-hosted-repo/simple --trusted-host nexus.mehes.gov.il)
FEED_HOST=xtfs.head.ad.mehes.gov.il

if [ -z "${FEED_TOKEN:-}" ]; then
    read -rsp "Azure DevOps feed token (for mlflowfunctions): " FEED_TOKEN
    echo
fi

python3.10 -m venv .venv
source .venv/bin/activate

# the order matters
pip install wheels/gunicorn-20.1.0-py3-none-any.whl "${NEXUS[@]}"
pip install wheels/pyarrow-12.0.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl "${NEXUS[@]}"
pip install wheels/urllib3-1.26.9-py3-none-any.whl "${NEXUS[@]}"
pip install wheels/mlflow-2.4.1-py3-none-any.whl "${NEXUS[@]}"
pip install -r requirements.txt "${NEXUS[@]}"
pip install mlflowfunctions \
    -i "https://${FEED_TOKEN}@${FEED_HOST}/DefaultCollection/general/_packaging/pypi_package/pypi/simple/" \
    --trusted-host "$FEED_HOST"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example - change what you need."
fi

echo
echo "Done. To run:"
echo "  source .venv/bin/activate"
echo "  python run_test.py"
