PYTHONWARNINGS=ignore::UserWarning \
python policy_lab/setup_policy_server.py \
    --port 10001 \
    --config_path policy_lab/replay_policy/deploy.yml \
    --overrides \
    --task_name demo_task \
    --ckpt_setting 0 \
    --seed 0 \
    --policy_name replay_policy \
    --data_path data/x-one/tianxing/3.hdf5
