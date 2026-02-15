"""模块：yt-dlp 下载视频。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable


def _run_download_impl(
    url: str,
    output_dir: Path,
    video_path: Path,
    *,
    force: bool,
    project_root: Path | None,
    extra_args: list[str],
    progress_callback: Callable[[str], None] | None,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未检测到 ffmpeg，请安装并加入 PATH")

    if video_path.is_file() and not force:
        return video_path

    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo+bestaudio", "--merge-output-format", "mp4",
        *extra_args,
        "-o", str(video_path), url,
    ]
    cwd = str(project_root) if project_root else str(output_dir.parent)

    if progress_callback is not None:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        last_lines: list[str] = []
        for line in proc.stdout:
            line = line.rstrip("\n\r")
            if line:
                last_lines.append(line)
                if len(last_lines) > 40:
                    last_lines.pop(0)
                progress_callback(line)
        proc.wait()
        if proc.returncode != 0:
            err = f"yt-dlp 退出码: {proc.returncode}"
            if last_lines:
                err += "\n\n" + "\n".join(last_lines[-25:])
            raise RuntimeError(err)
    else:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            err_parts = []
            if (r.stderr or "").strip():
                err_parts.append(r.stderr.strip())
            if (r.stdout or "").strip():
                err_parts.append(r.stdout.strip())
            err = "\n".join(err_parts)
            if err:
                lines = err.splitlines()
                if len(lines) > 25:
                    lines = ["..."] + lines[-24:]
                raise RuntimeError(f"yt-dlp 退出码: {r.returncode}\n\n" + "\n".join(lines))
            raise RuntimeError(f"yt-dlp 退出码: {r.returncode}")

    if not video_path.is_file():
        raise RuntimeError("下载后未得到 video.mp4")
    return video_path


def run_download(
    url: str,
    output_dir: Path,
    *,
    force: bool = False,
    project_root: Path | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | Path | None = None,
    js_runtime: str | None = None,
    remote_components: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> Path:
    """下载到 output_dir/video.mp4；已有且未 force 则跳过。progress_callback 可接收每行输出。
    cookies_from_browser / cookies_file: 见上。js_runtime: 如 'node' 传 --js-runtimes node。remote_components: 如 'ejs:github' 传 --remote-components。"""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "video.mp4"
    extra_args: list[str] = []
    cfile = Path(cookies_file).resolve() if cookies_file else None
    if cfile and cfile.is_file():
        extra_args.extend(["--cookies", str(cfile)])
    elif cookies_from_browser and cookies_from_browser.strip():
        extra_args.extend(["--cookies-from-browser", cookies_from_browser.strip()])
    if js_runtime and js_runtime.strip():
        extra_args.extend(["--js-runtimes", js_runtime.strip()])
    if remote_components and remote_components.strip():
        extra_args.extend(["--remote-components", remote_components.strip()])
    return _run_download_impl(
        url, output_dir, video_path,
        force=force, project_root=project_root,
        extra_args=extra_args, progress_callback=progress_callback,
    )


def run_download_preview(
    url: str,
    output_dir: Path,
    *,
    duration_sec: int = 120,
    project_root: Path | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | Path | None = None,
    js_runtime: str | None = None,
    remote_components: str | None = None,
) -> Path:
    """
    只下载前 duration_sec 秒作为预览片段，保存到 output_dir/preview_clip.mp4。
    用于不下载完整视频时也能拖动时间轴看裁剪效果。
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / "preview_clip.mp4"

    if not shutil.which("ffmpeg"):
        raise RuntimeError("未检测到 ffmpeg，请安装并加入 PATH")

    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo+bestaudio", "--merge-output-format", "mp4",
        "-t", str(duration_sec),
    ]
    cfile = Path(cookies_file).resolve() if cookies_file else None
    if cfile and cfile.is_file():
        cmd += ["--cookies", str(cfile)]
    elif cookies_from_browser and cookies_from_browser.strip():
        cmd += ["--cookies-from-browser", cookies_from_browser.strip()]
    if js_runtime and js_runtime.strip():
        cmd += ["--js-runtimes", js_runtime.strip()]
    if remote_components and remote_components.strip():
        cmd += ["--remote-components", remote_components.strip()]
    cmd += ["-o", str(preview_path), url]

    cwd = str(project_root) if project_root else str(output_dir.parent)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        err_parts = []
        if (r.stderr or "").strip():
            err_parts.append(r.stderr.strip())
        if (r.stdout or "").strip():
            err_parts.append(r.stdout.strip())
        err = "\n".join(err_parts)
        if err:
            lines = err.splitlines()
            if len(lines) > 25:
                lines = ["..."] + lines[-24:]
            raise RuntimeError(f"yt-dlp 退出码: {r.returncode}\n\n" + "\n".join(lines))
        raise RuntimeError(f"yt-dlp 退出码: {r.returncode}")
    if not preview_path.is_file():
        raise RuntimeError("下载后未得到 preview_clip.mp4")
    return preview_path
