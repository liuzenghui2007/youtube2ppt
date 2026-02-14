"""evp 相关：解析帧时间、从原视频抽帧、多图合成 PDF。"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


EVP_TMP_DIR = ".extract-video-ppt-tmp-data"


def parse_evp_frame_timestamps(output_dir: Path) -> list[float]:
    """从 evp 临时目录中的帧文件名解析时间戳（秒）。"""
    tmp = Path(output_dir) / EVP_TMP_DIR
    if not tmp.is_dir():
        return []
    # 例: frame00:00:01-0.56.jpg -> 1.0 秒
    pattern = re.compile(r"frame(\d{2}):(\d{2}):(\d{2})[-.]")
    times = []
    for f in tmp.iterdir():
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        m = pattern.match(f.stem)
        if m:
            h, m_, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            times.append(h * 3600 + m_ * 60 + s)
    return sorted(times)


def extract_frames_at_times(
    video_path: Path,
    times_sec: list[float],
    output_dir: Path,
) -> list[Path]:
    """在给定时间点从视频抽帧，保存为 frame_001.png 等，返回路径列表。"""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, t in enumerate(times_sec):
        out = output_dir / f"frame_{i + 1:03d}.png"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(out)],
            capture_output=True,
        )
        if r.returncode == 0 and out.is_file():
            paths.append(out)
    return paths


def frames_to_pdf(image_paths: list[Path], pdf_path: Path, *, size_wh: tuple[int, int] | None = None) -> None:
    """多张图片合成一个 PDF（fpdf2，兼容 extract-video-ppt 的用法）。"""
    from fpdf import FPDF

    if not image_paths:
        raise ValueError("无图片可合成")
    pdf = FPDF()
    pdf.compress = False
    # 默认横向、按第一张图尺寸；或传入 size_wh (w, h)
    for img_path in image_paths:
        # 简单按单页一图；fpdf2 旧 API add_page(format=(h,w)) 横向
        if size_wh:
            w, h = size_wh
            pdf.add_page(orientation="L", format=(h, w))
        else:
            pdf.add_page(orientation="L")
        pdf.image(name=str(img_path), x=0, y=0, w=pdf.w, h=pdf.h)
    # 旧 API: output(path, "F")
    pdf.output(str(pdf_path), "F")
