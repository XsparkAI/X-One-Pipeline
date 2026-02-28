PYTHONWARNINGS=ignore::UserWarning \
python policy_lab/setup_policy_server.py \
    --port 10001 \
    --config_path policy_lab/move_point_policy/deploy.yml \
    --overrides \
    --policy_name move_point_policy \
    # --task_name meituanbox \
    # --train_config_name "pi05_full_base" \
    # --model_path "/home/xspark-ai/project/openpi_ckpts/meituan_box_jan9_30000/"