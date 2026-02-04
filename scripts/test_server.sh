PYTHONWARNINGS=ignore::UserWarning \
python policy_lab/setup_policy_server.py \
    --port 10001 \
    --config_path policy_lab/demo_policy/deploy.yml \
    --overrides \
    --task_name demo_task \
    --collect_cfg dual_test_robot \
    --ckpt_setting 0 \
    --seed 0 \
    --policy_name demo_policy