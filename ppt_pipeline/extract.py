"""模块：用 evp 检测翻页，生成仅 PPT 区域 / 全屏 两种 PDF。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import evp_utils


def _hms_to_seconds(hms: str) -> int | None:
    if not hms or hms.strip() == "":
        return None
    parts = hms.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except ValueError:
        return None


def run_extract(
    output_dir: Path,
    video_full: Path,
    video_cropped: Path | None,
    crop: tuple[float, float, float, float] | None,
    similarity: float,
    start_time: str,
    end_time: str,
    output_ppt_only: bool,
    output_full_screen: bool,
    extract_images: bool,
    project_root: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    """
    检测用裁剪视频跑 evp；合成可选「仅 PPT 区域」和「全屏」。
    progress_callback 可接收 evp 的每行输出（如 process: 45%）。
    """
    output_dir = Path(output_dir).resolve()
    video_for_evp = video_cropped if video_cropped and video_cropped.is_file() else video_full
    env = os.environ.copy()
    env.setdefault("OPENCV_FFMPEG_READ_ATTEMPTS", "16384")

    pdfname_evp = "slides_evp.pdf"
    evp_cmd = [
        "evp",
        "--similarity", str(similarity),
        "--pdfname", pdfname_evp,
        str(output_dir),
        str(video_for_evp),
    ]
    if start_time:
        evp_cmd += ["--start_frame", start_time]
    if end_time:
        evp_cmd += ["--end_frame", end_time]

    if progress_callback is not None:
        proc = subprocess.Popen(
            evp_cmd,
            env=env,
            cwd=str(output_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n\r")
            if line:
                progress_callback(line)
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"evp 退出码: {proc.returncode}")
    else:
        r = subprocess.run(evp_cmd, env=env, cwd=str(output_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(f"evp 退出码: {r.returncode}")

    evp_pdf = output_dir / pdfname_evp  # evp 在 cwd=output_dir 下生成
    if not evp_pdf.is_file():
        raise RuntimeError("evp 未生成 PDF")

    result: dict[str, Path] = {}

    if output_ppt_only:
        out_ppt = output_dir / "slides_ppt_only.pdf"
        shutil.copy(evp_pdf, out_ppt)
        result["slides_ppt_only"] = out_ppt
        if extract_images:
            img_dir = output_dir / "images_ppt_only"
            img_dir.mkdir(parents=True, exist_ok=True)
            _pdf_to_images(out_ppt, img_dir, project_root)
            result["images_ppt_only"] = img_dir

    if output_full_screen and video_full.is_file():
        times = evp_utils.parse_evp_frame_timestamps(output_dir)
        if not times:
            # evp 临时目录可能已被清理，无法生成全屏
            pass
        else:
            full_frames_dir = output_dir / "frames_full"
            full_frames_dir.mkdir(parents=True, exist_ok=True)
            paths = evp_utils.extract_frames_at_times(video_full, times, full_frames_dir)
            if paths:
                out_full = output_dir / "slides_full.pdf"
                evp_utils.frames_to_pdf(paths, out_full)
                result["slides_full"] = out_full
                if extract_images:
                    img_dir = output_dir / "images_full"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    for i, p in enumerate(paths, 1):
                        shutil.copy(p, img_dir / f"page_{i:03d}.png")
                    result["images_full"] = img_dir

    return result


def _pdf_to_images(pdf_path: Path, out_dir: Path, project_root: Path | None) -> None:
    try:
        import fitz
    except ImportError:
        return
    doc = fitz.open(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(len(doc)):
        doc[i].get_pixmap(dpi=150).save(out_dir / f"page_{i + 1:03d}.png")
    doc.close()
