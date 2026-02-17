# 场景参数扫描（无头）

`run_scene_param_sweep.py` 用多组场景检测参数分别跑一次提取，每组结果放到独立子目录，方便对比「页数多少、是否漏检」。

## 用法

在项目根目录下，**用本项目的虚拟环境**运行（否则会缺 cv2/scenedetect）：

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe scripts\run_scene_param_sweep.py

# 或先激活 venv 再跑
.\.venv\Scripts\Activate.ps1
python scripts/run_scene_param_sweep.py
```

可选参数：

- `--video-dir ./video_output`  视频目录（默认 `./video_output`，需已有 `video.mp4`）
- `--out-base ./ppt_output/param_sweep`  结果根目录（默认 `./ppt_output/param_sweep`）
- `--crop "0.265,0,0.735,1"`  裁剪区域，不传则用 `config.json` 里的 crop_*

## 参数组说明

| 子目录 | 说明 | 大致倾向 |
|--------|------|----------|
| 01_default | 默认参数 | 平衡 |
| 02_sensitive | 更敏感 | 页数多、可能多误检 |
| 03_medium | 中等敏感 + 关过滤 | 页数偏多 |
| 04_low_filter | 默认阈值、关静态/重复 | 看过滤影响 |
| 05_conservative | 保守 | 页数少、更稳 |
| 06_very_sensitive | 非常敏感 | 页数最多、易重复 |

跑完后终端会打印「汇总」：按帧数排序，便于一眼看出哪组检出最多。各子目录内为完整提取结果（frames_scenedetect、images_ppt_only、PDF、PPTX 等）。
