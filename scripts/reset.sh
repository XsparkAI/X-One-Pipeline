#!/usr/bin/env bash
set -euo pipefail

collect_cfg="${1:?collect_cfg required}"

python pipeline/reset.py --collect_cfg "${collect_cfg}"
