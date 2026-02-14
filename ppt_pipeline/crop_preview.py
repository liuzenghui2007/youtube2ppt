"""裁剪与预览：ffmpeg 裁剪、生成带红线框的预览帧。"""
from __future__ import annotations

import subprocess
from pathlib import Path


def parse_crop(s: str) -> tuple[float, float, float, float]:
    """解析 "left,top,width,height" 为 0~1 比例。"""
    parts = [x.strip() for x in s.split(",")]
    if len(parts) != 4:
        raise ValueError('格式为 "left,top,width,height"，例如 "0.35,0,0.65,1"')
    vals = []
    for i, p in enumerate(parts):
        try:
            v = float(p)
        except ValueError:
            raise ValueError(f"第 {i+1} 项须为数字: {p!r}")
        if not 0 <= v <= 1:
            raise ValueError(f"各项须在 0~1 之间: {s}")
        vals.append(v)
    left, top, width, height = vals
    if width <= 0 or height <= 0:
        raise ValueError("width 与 height 须大于 0")
    if left + width > 1 or top + height > 1:
        raise ValueError("left+width、top+height 不能超过 1")
    return left, top, width, height


def get_video_duration_sec(video_path: Path) -> float:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {r.stderr}")
    return float(r.stdout.strip())


def run_crop(
    video_path: Path,
    output_dir: Path,
    crop: tuple[float, float, float, float],
    *,
    force: bool = False,
) -> Path:
    """生成 output_dir/video_cropped.mp4；已有且未 force 则跳过。"""
    video_path = Path(video_path)
    output_dir = Path(output_dir).resolve()
    cropped_path = output_dir / "video_cropped.mp4"
    if cropped_path.is_file() and not force:
        return cropped_path

    left, top, width, height = crop
    vf = f"crop=iw*{width}:ih*{height}:iw*{left}:ih*{top}"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf, "-c:a", "copy", str(cropped_path)],
        capture_output=True,
    )
    if r.returncode != 0 or not cropped_path.is_file():
        raise RuntimeError(f"ffmpeg 裁剪失败: {r.stderr.decode(errors='replace')}")
    return cropped_path


def run_preview_frames(
    video_path: Path,
    output_dir: Path,
    crop: tuple[float, float, float, float],
    num_frames: int = 3,
) -> list[Path]:
    """从视频中间取 num_frames 帧，画红线框，保存 crop_preview_01.png 等。"""
    try:
        import cv2
    except ImportError:
        raise RuntimeError("预览需要 opencv（extract-video-ppt 已依赖）")

    duration = get_video_duration_sec(video_path)
    left, top, width, height = crop
    times = [duration * (i + 1) / (num_frames + 1) for i in range(num_frames)]
    out_paths = []

    for i, t in enumerate(times):
        raw_path = output_dir / f"_crop_preview_{i + 1:02d}.png"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(raw_path)],
            capture_output=True,
        )
        if r.returncode != 0 or not raw_path.is_file():
            continue
        img = cv2.imread(str(raw_path))
        if img is None:
            raw_path.unlink(missing_ok=True)
            continue
        h, w = img.shape[:2]
        x1, x2 = int(left * w), int((left + width) * w)
        y1, y2 = int(top * h), int((top + height) * h)
        color = (0, 0, 255)
        thick = max(2, min(w, h) // 400)
        cv2.line(img, (0, y1), (w, y1), color, thick)
        cv2.line(img, (0, y2), (w, y2), color, thick)
        cv2.line(img, (x1, 0), (x1, h), color, thick)
        cv2.line(img, (x2, 0), (x2, h), color, thick)
        final_path = output_dir / f"crop_preview_{i + 1:02d}.png"
        cv2.imwrite(str(final_path), img)
        out_paths.append(final_path)
        raw_path.unlink(missing_ok=True)
    return out_paths


def get_frame_at_time(video_path: Path, time_sec: float) -> bytes | None:
    """从视频 time_sec 处取一帧，返回 PNG 字节（用于 GUI 预览）。"""
    r = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(time_sec), "-i", str(video_path), "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    )
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout
