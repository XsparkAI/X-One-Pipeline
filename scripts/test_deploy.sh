set -euo pipefail

task_name="${1:?task_name required}"
policy_name="${2:?policy_name required}"
deploy_cfg="${3:?deploy_cfg required}"
collect_cfg="${4:?collect_cfg required}"
shift 4

python pipeline/test_deploy.py \
    --task_name "${task_name}" \
    --policy_name "${policy_name}" \
    --deploy_cfg "${deploy_cfg}" \
    --collect_cfg "${collect_cfg}" \
    "$@"
