PYTHONWARNINGS=ignore::UserWarning \
python policy_lab/setup_policy_server.py \
    --port 10001 \
    --config_path policy_lab/openpi_policy/deploy.yml \
    --overrides \
    --task_name meituanbox \
    --policy_name openpi_policy \
    --train_config_name "pi05_full_base" \
    --model_path "/home/xspark-ai/project/openpi_ckpts/meituan_box_jan9_30000/"