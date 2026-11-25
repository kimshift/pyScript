# -*- coding: utf-8 -*-
"""OCR 主通道：PNG → 文字节点（RapidOCR，自带模型，无需联网）。

为什么 OCR 是主通道
-------------------
视频广告是持续渲染的 SurfaceView，`uiautomator` 永远等不到 idle，必失败；
而且奖励弹窗是覆盖层，不在活动窗口里，uiautomator 读不到「领取奖励」。
所以识别一律以截图 + OCR 为准，uiautomator 只做兜底（见 uia.py）。

兼容两代包名：`rapidocr_onnxruntime`（1.x，返回 (result, elapse)）与
`rapidocr`（2.x，返回带 boxes/txts/scores 的对象），调用方无感。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from tools.qishui_auto.match import Node


def decode_png(data: bytes):
    """PNG 字节 → BGR ndarray；失败返回 None。"""
    import cv2
    import numpy as np

    if not data:
        return None
    buffer = np.frombuffer(data, dtype=np.uint8)
    if buffer.size == 0:
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def read_image(path: Path):
    """按 Unicode 路径读图（cv2.imread 在中文路径下会返回 None）。"""
    import cv2
    import numpy as np

    buffer = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR) if buffer.size else None


class OcrEngine:
    """懒加载的 OCR 引擎：第一次调用才加载模型（约 0.3~1s）。"""

    def __init__(self, min_score: float = 0.5, max_width: int = 720, use_cls: bool = False):
        self.min_score = min_score
        self.max_width = max(320, int(max_width))
        self.use_cls = use_cls
        self._engine = None
        self._mode = ""

    # ---------- 可用性 ----------

    @staticmethod
    def deps_status() -> tuple[bool, str]:
        """检查依赖是否齐全，返回 (可用, 说明)。"""
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError as exc:
            return False, f"缺少 {exc.name}（mise run qs:setup）"
        try:
            from rapidocr_onnxruntime import RapidOCR

            return True, "rapidocr-onnxruntime"
        except ImportError:
            pass
        try:
            from rapidocr import RapidOCR  # noqa: F401

            return True, "rapidocr(2.x)"
        except ImportError:
            return False, "缺少 rapidocr-onnxruntime（mise run qs:setup）"

    def _load(self):
        if self._engine is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
            self._mode = "legacy"
        except ImportError:
            from rapidocr import RapidOCR

            self._engine = RapidOCR()
            self._mode = "v2"

    def warmup(self) -> float:
        """加载模型并跑一张空白图，返回耗时秒数（check 用）。"""
        import numpy as np

        start = time.time()
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        self.nodes(blank)
        return time.time() - start

    # ---------- 识别 ----------

    def nodes(self, image, crop: tuple[float, float] | None = None) -> list[Node]:
        """返回按屏幕像素坐标表示的文本节点（已过滤低置信度）。

        crop=(top, bottom) 时只识别这一段纵向区域（0~1 相对坐标），坐标仍还原成
        整屏坐标。底部商品卡/聊天区占屏幕三成，里面几十行字全都要跑识别，
        裁掉后同样的截图 OCR 从 ~3.2s 降到 ~1.4s。默认 None = 整屏（check 用）。
        """
        import cv2
        import numpy as np

        if image is None or getattr(image, "size", 0) == 0:
            return []

        height, width = image.shape[:2]
        offset_y = 0
        source = image
        if crop:
            top, bottom = (min(1.0, max(0.0, float(v))) for v in crop)
            y1 = int(height * top)
            y2 = int(height * bottom)
            if y2 - y1 >= 16 and (y1 > 0 or y2 < height):  # 太小的裁剪没意义，忽略
                source = image[y1:y2, :]
                offset_y = y1

        height, width = source.shape[:2]
        scale = 1.0
        target = source
        if width > self.max_width:  # 缩到固定宽度，小字还能看清又不拖慢
            scale = self.max_width / float(width)
            target = cv2.resize(source, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)

        self._load()
        rows = self._infer(target)
        inv = 1.0 / scale
        nodes: list[Node] = []
        for box, text, score in rows:
            if not text or score < self.min_score:
                continue
            pts = np.array(box, dtype=np.float32).reshape(-1, 2) * inv
            xs, ys = pts[:, 0], pts[:, 1] + offset_y
            nodes.append(
                Node(
                    label=str(text),
                    cx=round(float(xs.mean())),
                    cy=round(float(ys.mean())),
                    x1=round(float(xs.min())),
                    y1=round(float(ys.min())),
                    x2=round(float(xs.max())),
                    y2=round(float(ys.max())),
                    score=float(score),
                )
            )
        return nodes

    def _infer(self, image) -> list[tuple[object, str, float]]:
        """统一两代返回值为 [(box, text, score), ...]。"""
        try:
            result = self._engine(image, use_cls=self.use_cls)
        except TypeError:  # 2.x 不接受 use_cls 参数
            result = self._engine(image)

        if self._mode == "legacy":
            rows, _ = result if isinstance(result, tuple) else (result, None)
            out = []
            for row in rows or []:
                if not row or len(row) < 3:
                    continue
                out.append((row[0], str(row[1]), float(row[2])))
            return out

        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        if boxes is None or texts is None:
            return []
        scores = [1.0] * len(texts) if scores is None else scores
        return [(box, str(text), float(score)) for box, text, score in zip(boxes, texts, scores)]


def save_debug(image, node_label: str, x: int, y: int, out_dir: Path, seq: int, action: str = "") -> Path | None:
    """把命中位置标在截图上存档，排查「点错位置」时直接看图。"""
    import re

    import cv2

    if image is None:
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        vis = image.copy()
        cv2.drawMarker(vis, (int(x), int(y)), (0, 0, 255), cv2.MARKER_CROSS, 60, 3)
        cv2.circle(vis, (int(x), int(y)), 28, (0, 0, 255), 3)
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", f"{action}_{node_label}")[:40]
        name = f"{datetime.now():%Y%m%d_%H%M%S}_{seq:04d}_{safe}_{x}_{y}.png"
        path = out_dir / name
        ok, buffer = cv2.imencode(".png", vis)
        if not ok:
            return None
        buffer.tofile(str(path))  # 走 ndarray.tofile 才能写中文路径
        return path
    except Exception:  # noqa: BLE001 - 调试图只是辅助，任何失败都不该打断主流程
        return None


# ------------------------- 调试图清理 -------------------------
# 一张标注截图 1~4MB，一小时就能攒几百 MB。规则分两层：
# 启动时清掉上一轮（默认全清，可留最新几张），运行中再按总量上限删最旧的。

_DEBUG_SUFFIXES = (".png", ".jpg", ".jpeg")


def _debug_files(out_dir: Path) -> list[Path]:
    """目录里的截图，按修改时间从旧到新。只认图片后缀，别误删手写的说明文件。"""
    if not out_dir.is_dir():
        return []
    items = [p for p in out_dir.iterdir() if p.is_file() and p.suffix.lower() in _DEBUG_SUFFIXES]
    return sorted(items, key=lambda p: (p.stat().st_mtime, p.name))


def _remove(paths: list[Path], log=None) -> tuple[int, int]:
    """删文件，返回 (删除数量, 释放字节数)。删不掉的（被查看器占用）跳过，不报错。"""
    count = freed = 0
    for path in paths:
        try:
            size = path.stat().st_size
            path.unlink()
            count += 1
            freed += size
        except OSError as exc:  # 文件被占用/权限不足：跳过，不影响主流程
            if log:
                log("调试图删不掉（已跳过）：%s（%s）", path.name, exc)
    return count, freed


def clear_debug_images(out_dir: Path, keep: int = 0, log=None) -> int:
    """启动前清空历史调试图，返回删掉的数量。

    keep>0 时保留最新的 keep 张（想留点现场排查就填几）。
    """
    files = _debug_files(out_dir)
    if keep:
        files = files[: max(0, len(files) - keep)]
    count, freed = _remove(files, log)
    if count and log:
        log("已清理上次的调试图 %d 张（释放 %.1fMB）", count, freed / 1024 / 1024)
    return count


def trim_debug_images(out_dir: Path, max_total_mb: float, log=None) -> int:
    """把目录总量压到 max_total_mb 以内（按修改时间删最旧的），返回删掉的数量。

    按「总量」而不是「张数」限制：截图大小随画面复杂度差好几倍，
    按张数管不住磁盘占用。
    """
    if max_total_mb <= 0:
        return 0
    limit = int(max_total_mb * 1024 * 1024)
    files = _debug_files(out_dir)
    sizes = {}
    total = 0
    for path in files:
        try:
            sizes[path] = path.stat().st_size
            total += sizes[path]
        except OSError:
            continue
    if total <= limit:
        return 0

    victims: list[Path] = []
    for path in files:  # 从最旧的开始删，直到回到上限内
        if total <= limit:
            break
        if path not in sizes:
            continue
        victims.append(path)
        total -= sizes[path]
    count, _ = _remove(victims, log)
    if count and log:
        log("调试图超过 %.0fMB，删除最旧的 %d 张", max_total_mb, count)
    return count
