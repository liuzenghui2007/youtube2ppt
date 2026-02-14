"""主窗口：左侧表单（URL、裁剪、参数、三按钮）+ 右侧视频预览（时间轴 + 裁剪框）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QScrollArea,
    QFrame,
    QPlainTextEdit,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QByteArray
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen

from ppt_pipeline import (
    load_config,
    save_config,
    run_download,
    run_crop,
    run_preview_frames,
    parse_crop,
    run_extract,
    get_video_duration_sec,
    get_frame_at_time,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Worker(QThread):
    finished = Signal(bool, str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class DownloadWorker(QThread):
    """带进度输出的下载 Worker。"""
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self, url: str, output_dir: Path, force: bool, project_root: Path):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.force = force
        self.project_root = project_root

    def run(self):
        try:
            run_download(
                self.url,
                self.output_dir,
                force=self.force,
                project_root=self.project_root,
                progress_callback=lambda line: self.progress.emit(line),
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ExtractWorker(QThread):
    """带进度输出的提取 Worker。"""
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(
        self,
        output_dir: Path,
        video_full: Path,
        video_cropped: Path | None,
        crop: tuple[float, float, float, float],
        similarity: float,
        start_time: str,
        end_time: str,
        output_ppt_only: bool,
        output_full_screen: bool,
        extract_images: bool,
        project_root: Path,
    ):
        super().__init__()
        self.output_dir = output_dir
        self.video_full = video_full
        self.video_cropped = video_cropped
        self.crop = crop
        self.similarity = similarity
        self.start_time = start_time
        self.end_time = end_time
        self.output_ppt_only = output_ppt_only
        self.output_full_screen = output_full_screen
        self.extract_images = extract_images
        self.project_root = project_root

    def run(self):
        try:
            from ppt_pipeline import run_crop
            v_crop = self.output_dir / "video_cropped.mp4"
            if not v_crop.is_file():
                self.progress.emit("正在裁剪视频…")
                run_crop(self.video_full, self.output_dir, self.crop, force=False)
            self.progress.emit("正在运行 evp 检测翻页…")
            run_extract(
                self.output_dir,
                self.video_full,
                v_crop if v_crop.is_file() else None,
                self.crop,
                self.similarity,
                self.start_time,
                self.end_time,
                self.output_ppt_only,
                self.output_full_screen,
                self.extract_images,
                self.project_root,
                progress_callback=lambda line: self.progress.emit(line),
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube 视频提取 PPT")
        self.setMinimumSize(960, 620)
        self.resize(1100, 700)
        self._project_root = PROJECT_ROOT
        self._cfg = load_config(self._project_root)
        self._video_path: Path | None = None
        self._duration_sec = 0.0
        self._worker: Worker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 左侧表单
        left = QWidget()
        left.setMaximumWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 12, 0)

        form = QFormLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_edit.setText(self._cfg.get("url", ""))
        form.addRow("URL:", self.url_edit)

        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setText(self._cfg.get("output_dir", "./ppt_output"))
        self.output_edit.editingFinished.connect(self._refresh_video_source)
        out_row.addWidget(self.output_edit)
        browse_btn = QPushButton("选择…")
        browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_btn)
        form.addRow("输出目录:", out_row)

        crop_row = QHBoxLayout()
        self.crop_left = QLineEdit()
        self.crop_left.setPlaceholderText("0.35")
        self.crop_left.setText(str(self._cfg.get("crop_left", 0.35)))
        self.crop_top = QLineEdit()
        self.crop_top.setPlaceholderText("0")
        self.crop_top.setText(str(self._cfg.get("crop_top", 0)))
        self.crop_width = QLineEdit()
        self.crop_width.setPlaceholderText("0.65")
        self.crop_width.setText(str(self._cfg.get("crop_width", 0.65)))
        self.crop_height = QLineEdit()
        self.crop_height.setPlaceholderText("1")
        self.crop_height.setText(str(self._cfg.get("crop_height", 1)))
        crop_row.addWidget(QLabel("L"))
        crop_row.addWidget(self.crop_left)
        crop_row.addWidget(QLabel("T"))
        crop_row.addWidget(self.crop_top)
        crop_row.addWidget(QLabel("W"))
        crop_row.addWidget(self.crop_width)
        crop_row.addWidget(QLabel("H"))
        crop_row.addWidget(self.crop_height)
        form.addRow("裁剪(L,T,W,H):", crop_row)

        self.similarity_edit = QLineEdit()
        self.similarity_edit.setText(str(self._cfg.get("similarity", 0.45)))
        form.addRow("相似度:", self.similarity_edit)

        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("00:00:00")
        self.start_edit.setText(self._cfg.get("start_time", ""))
        form.addRow("开始时间:", self.start_edit)

        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("留空到结尾")
        self.end_edit.setText(self._cfg.get("end_time", ""))
        form.addRow("结束时间:", self.end_edit)

        self.check_ppt_only = QCheckBox("导出仅 PPT 区域 PDF")
        self.check_ppt_only.setChecked(bool(self._cfg.get("output_ppt_only", True)))
        form.addRow("", self.check_ppt_only)

        self.check_full = QCheckBox("导出全屏 PDF")
        self.check_full.setChecked(bool(self._cfg.get("output_full_screen", False)))
        form.addRow("", self.check_full)

        self.check_images = QCheckBox("导出单页图片")
        self.check_images.setChecked(bool(self._cfg.get("extract_images", True)))
        form.addRow("", self.check_images)

        left_layout.addLayout(form)

        # 三个主按钮
        btn_layout = QVBoxLayout()
        self.btn_download = QPushButton("下载")
        self.btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self.btn_download)

        self.btn_preview = QPushButton("预览")
        self.btn_preview.clicked.connect(self._on_preview)
        btn_layout.addWidget(self.btn_preview)

        self.btn_extract = QPushButton("提取")
        self.btn_extract.clicked.connect(self._on_extract)
        btn_layout.addWidget(self.btn_extract)

        save_cfg_btn = QPushButton("保存设置")
        save_cfg_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(save_cfg_btn)

        left_layout.addLayout(btn_layout)
        left_layout.addStretch()
        layout.addWidget(left)

        # 右侧：视频预览（上，主） + 下载进度（下，可拖拽调节）
        right = QFrame()
        right.setFrameStyle(QFrame.Shape.StyledPanel)
        right_main = QVBoxLayout(right)
        right_main.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 视频区域（上方，占大部分空间）
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setText("请先下载视频\n下载后可在右侧拖动时间轴查看裁剪效果")
        self.preview_label.setStyleSheet("background: #2d2d2d; color: #888; font-size: 13px;")
        video_layout.addWidget(self.preview_label, stretch=1)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 10000)
        self.time_slider.setValue(0)
        self.time_slider.valueChanged.connect(self._on_slider_changed)
        video_layout.addWidget(self.time_slider)

        time_row = QHBoxLayout()
        self.time_label = QLabel("0:00 / 0:00")
        time_row.addWidget(self.time_label)
        refresh_btn = QPushButton("刷新预览")
        refresh_btn.setToolTip("重新检测输出目录中的 video.mp4，若已下载会显示预览")
        refresh_btn.clicked.connect(self._refresh_video_source)
        time_row.addStretch()
        time_row.addWidget(refresh_btn)
        video_layout.addLayout(time_row)

        splitter.addWidget(video_widget)

        # 下载进度（下方，默认较小，可拖动分割条调整）
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.addWidget(QLabel("下载进度:"))
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(56)
        self.log_text.setPlaceholderText("下载时会在此显示 yt-dlp 进度…")
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_widget)

        # 默认比例：视频区占大部分，进度区约 100px
        splitter.setSizes([500, 100])
        right_main.addWidget(splitter)
        layout.addWidget(right, stretch=1)

        self._output_dir = None
        self._refresh_video_source()

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text())
        if d:
            self.output_edit.setText(d)
            self._refresh_video_source()

    def _get_output_dir(self) -> Path:
        raw = (self.output_edit.text() or "").strip() or "./ppt_output"
        p = Path(raw)
        if not p.is_absolute():
            p = self._project_root / p
        return p.resolve()

    def _get_crop(self) -> tuple[float, float, float, float]:
        try:
            l_ = float(self.crop_left.text() or "0.35")
            t = float(self.crop_top.text() or "0")
            w = float(self.crop_width.text() or "0.65")
            h = float(self.crop_height.text() or "1")
            return (l_, t, w, h)
        except ValueError:
            return (0.35, 0, 0.65, 1)

    def _refresh_video_source(self):
        out = self._get_output_dir()
        video = out / "video.mp4"
        if video.is_file():
            self._video_path = video
            try:
                self._duration_sec = get_video_duration_sec(video)
                self.time_slider.setEnabled(True)
                self._on_slider_changed(self.time_slider.value())
            except Exception:
                self._duration_sec = 0
                self.time_slider.setEnabled(False)
                self.preview_label.setText("无法读取视频时长")
        else:
            self._video_path = None
            self._duration_sec = 0
            self.time_slider.setEnabled(False)
            self.preview_label.setText(
                "请先下载视频\n下载后可在右侧拖动时间轴查看裁剪效果\n\n"
                f"当前查找: {video}"
            )
            self.time_label.setText("0:00 / 0:00")

    def _on_slider_changed(self, val: int):
        if not self._video_path or self._duration_sec <= 0:
            return
        t = (val / 10000.0) * self._duration_sec
        self.time_label.setText(f"{_fmt_time(t)} / {_fmt_time(self._duration_sec)}")
        data = get_frame_at_time(self._video_path, t)
        if not data:
            return
        img = QImage()
        img.loadFromData(QByteArray(data), "PNG")
        if img.isNull():
            return
        crop = self._get_crop()
        w, h = img.width(), img.height()
        x1 = int(crop[0] * w)
        x2 = int((crop[0] + crop[2]) * w)
        y1 = int(crop[1] * h)
        y2 = int((crop[1] + crop[3]) * h)
        painter = QPainter(img)
        painter.setPen(QPen(QColor(255, 0, 0), max(2, min(w, h) // 200)))
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)
        painter.end()
        pix = QPixmap.fromImage(img)
        self.preview_label.setPixmap(pix.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _write_config_to_disk(self, *, show_message: bool = False):
        """把当前表单写入 config.json。"""
        self._cfg["url"] = self.url_edit.text().strip()
        self._cfg["output_dir"] = self.output_edit.text().strip() or "./ppt_output"
        try:
            self._cfg["crop_left"] = float(self.crop_left.text() or "0.35")
            self._cfg["crop_top"] = float(self.crop_top.text() or "0")
            self._cfg["crop_width"] = float(self.crop_width.text() or "0.65")
            self._cfg["crop_height"] = float(self.crop_height.text() or "1")
            self._cfg["similarity"] = float(self.similarity_edit.text() or "0.45")
        except ValueError:
            pass
        self._cfg["start_time"] = self.start_edit.text().strip()
        self._cfg["end_time"] = self.end_edit.text().strip()
        self._cfg["output_ppt_only"] = self.check_ppt_only.isChecked()
        self._cfg["output_full_screen"] = self.check_full.isChecked()
        self._cfg["extract_images"] = self.check_images.isChecked()
        save_config(self._cfg, self._project_root)
        if show_message:
            QMessageBox.information(self, "保存", "设置已保存到 config.json")

    def _save_config(self):
        self._write_config_to_disk(show_message=True)

    def closeEvent(self, event):
        """关闭窗口时自动保存左侧设置，下次启动自动恢复。"""
        self._write_config_to_disk(show_message=False)
        super().closeEvent(event)

    def _set_buttons_enabled(self, en: bool):
        self.btn_download.setEnabled(en)
        self.btn_preview.setEnabled(en)
        self.btn_extract.setEnabled(en)

    def _on_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请填写 URL")
            return
        out = self._get_output_dir()
        self._set_buttons_enabled(False)
        self.log_text.clear()
        self.log_text.appendPlainText("开始下载…\n")
        self._worker = DownloadWorker(
            url, out,
            force=self._cfg.get("force_download"),
            project_root=self._project_root,
        )
        self._worker.progress.connect(self._append_download_log)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _append_download_log(self, line: str):
        self.log_text.appendPlainText(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _on_preview(self):
        out = self._get_output_dir()
        video = out / "video.mp4"
        if not video.is_file():
            QMessageBox.warning(self, "提示", "请先下载视频")
            return
        try:
            crop = self._get_crop()
        except ValueError as e:
            QMessageBox.warning(self, "提示", str(e))
            return
        self._set_buttons_enabled(False)
        def do():
            run_crop(video, out, crop, force=self._cfg.get("force_crop"))
            run_preview_frames(video, out, crop)
        self._worker = Worker(do)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_extract(self):
        out = self._get_output_dir()
        video_full = out / "video.mp4"
        video_cropped = out / "video_cropped.mp4"
        if not video_full.is_file():
            QMessageBox.warning(self, "提示", "请先下载视频")
            return
        try:
            get_video_duration_sec(video_full)
        except Exception:
            QMessageBox.warning(
                self,
                "视频文件无效",
                "当前 video.mp4 可能不完整或已损坏（例如下载曾中断）。\n\n"
                "请删除输出目录下的 video.mp4，然后重新点击「下载」再试。",
            )
            return
        try:
            crop = self._get_crop()
            sim = float(self.similarity_edit.text() or "0.45")
        except ValueError as e:
            QMessageBox.warning(self, "提示", str(e))
            return
        self._set_buttons_enabled(False)
        self.log_text.clear()
        self.log_text.appendPlainText("开始提取（evp 检测翻页 + 生成 PDF）…\n")
        self._worker = ExtractWorker(
            out,
            video_full,
            video_cropped if video_cropped.is_file() else None,
            crop,
            sim,
            self.start_edit.text().strip(),
            self.end_edit.text().strip(),
            self.check_ppt_only.isChecked(),
            self.check_full.isChecked(),
            self.check_images.isChecked(),
            self._project_root,
        )
        self._worker.progress.connect(self._append_download_log)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, ok: bool, err: str):
        self._set_buttons_enabled(True)
        if ok:
            if self.log_text.toPlainText().strip():
                self.log_text.appendPlainText("\n完成。")
            self._refresh_video_source()
            QMessageBox.information(self, "完成", "操作已完成")
        else:
            if self.log_text.toPlainText().strip():
                self.log_text.appendPlainText(f"\n失败: {err}")
            QMessageBox.critical(self, "错误", err or "未知错误")
        self._worker = None


def _fmt_time(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"
