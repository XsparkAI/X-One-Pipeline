PYTHONWARNINGS=ignore::UserWarning \
python pipeline/deploy_local.py \
    --task_name demo_task \
    --policy_name openpi_policy \
    --base_cfg x-one \
    --config_path policy_lab/openpi_policy/deploy.yml \
    --overrides \
    --train_config_name "pi05_full_base" \
    --model_path "/home/xspark-ai/project/openpi_ckpts/meituan_box_jan9_30000/"