# replay_robotwin的步骤

## replay and record
```bash
python replay_robotwin.py --base_cfg_path ./config/x-one.yml --robotwin_data_path ./data/cover_blocks/demo_clean/ --idx 0
```
注意：idx根据实际而定

## 获取视频
获取回放时的视频
```bash
bash scripts/vis_data.sh cover_blocks x-one 0 data/cover_blocks/x-one/video/episode0.mp4 
```

批量获取回放时的视频
```bash
bash scripts/vis_data_batch.sh cover_blocks x-one 
```

## 转换格式
```bash
python convert2act_hdf5.py data/place_shoe/ data/place_shoe_act/ --num_worker 3
```