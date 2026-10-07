# HS classifier test

Sends each product in `test-data/test_products.json` to the `hscode_manager` agent, scores the returned HS code, and logs the results to MLflow.

Needs Linux (or WSL) with Python 3.10: the pyarrow wheel in `wheels/` is built for that.

## Steps

1. Set up once. This creates `.venv`, installs the wheels in `wheels/` and the rest, and creates `.env`. It asks for the Azure DevOps feed token that `mlflowfunctions` installs from.
   ```
   ./setup.sh
   ```
2. Edit `.env` if needed. The defaults call the dev agent once over the whole test set.
3. Run:
   ```
   source .venv/bin/activate
   python run_test.py
   ```

Results go to MLflow and to `results/`, which each run overwrites.

To send a single request to the agent by hand, edit and run `request-example/request-manager.py`. It writes the response to `tmp.json`.
