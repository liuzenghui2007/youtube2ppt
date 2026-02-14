# YouTube 视频提取 PPT

模块化流水线 + PySide6 GUI：下载 → 预览/裁剪 → 提取（仅 PPT 区域 / 全屏 PDF）。

## 依赖

- Python 3.10+
- ffmpeg（需在 PATH）
- uv（推荐）

## 安装与运行

```bash
uv sync
uv run main.py
```

默认启动 GUI。命令行模式：

```bash
uv run main.py --cli --download -u "https://www.youtube.com/watch?v=xxx" -o ./ppt_output
uv run main.py --cli --preview --crop "0.35,0,0.65,1" -o ./ppt_output
uv run main.py --cli --extract -o ./ppt_output
```

## GUI

- 左侧：URL、输出目录、裁剪比例 (L,T,W,H)、相似度、时间范围、导出选项，以及三个按钮：**下载**、**预览**、**提取**。
- 右侧：视频预览；有视频时可拖动时间轴查看当前帧，并叠加裁剪框红线。
- 设置可保存到项目根目录 `config.json`。

## 输出

- `video.mp4`：下载的原视频
- `video_cropped.mp4`：裁剪后视频（用于检测翻页）
- `crop_preview_*.png`：裁剪区域预览图（红线框）
- `slides_ppt_only.pdf` / `slides_full.pdf`：仅 PPT 区域 / 全屏 PDF
- `images_ppt_only/`、`images_full/`：单页图片（可选）
