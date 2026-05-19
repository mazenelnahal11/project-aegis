#!/bin/bash
# Seeds the Aegis demo with synthetic rogue processes + world-writable files
# so the dashboard has something to detect. Runs inside the backend container.
#
# Spawned processes are all `sleep`-based (no real CPU/IO load) but their
# *recorded* runtime + a tiny on-host shenanigan make Aegis flag them.

set -e

# Create the simulated /home/<student>/ folders with some world-writable files.
mkdir -p /tmp/aegis_demo/home_mock/alice
mkdir -p /tmp/aegis_demo/home_mock/bob
echo "secret tokens here" > /tmp/aegis_demo/home_mock/alice/api_keys.txt
chmod 777 /tmp/aegis_demo/home_mock/alice/api_keys.txt
echo "raw dataset"        > /tmp/aegis_demo/home_mock/bob/dataset.csv
chmod 777 /tmp/aegis_demo/home_mock/bob/dataset.csv
chmod 777 /tmp/aegis_demo/home_mock/alice

# Spawn long-running fake processes. Names mimic what students actually run.
# Aegis flags them via the runtime/CPU thresholds — for the demo we lie about
# CPU by occupying it briefly, but mostly the runtime detection does the work.
nohup bash -c 'exec -a "python train.py" sleep 999999' >/dev/null 2>&1 &
nohup bash -c 'exec -a "jupyter-notebook" sleep 999999' >/dev/null 2>&1 &
nohup bash -c 'exec -a "stress-ng --cpu 4" sleep 999999' >/dev/null 2>&1 &

echo "[seed] demo processes + world-writable files in place"
