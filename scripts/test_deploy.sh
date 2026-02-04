set -euo pipefail

task_name="${1:?task_name required}"
policy_name="${2:?policy_name required}"
collect_cfg="${3:?collect_cfg required}"
shift 3

python pipeline/test_deploy.py \
    --task_name "${task_name}" \
    --policy_name "${policy_name}" \
    --collect_cfg "${collect_cfg}" \
    "$@"
