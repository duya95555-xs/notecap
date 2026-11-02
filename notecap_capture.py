#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截图后端统一结果协议；不依赖 tkinter，不直接写最终笔记目录。"""

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None


SUCCESS = "success"
CANCELLED = "cancelled"
FAILED = "failed"


@dataclass(frozen=True)
class CaptureResult:
    status: str
    image: object = None
    backend: str = "builtin"
    code: str = ""
    message: str = ""

    @property
    def ok(self):
        return self.status == SUCCESS


def cancelled(backend="builtin"):
    return CaptureResult(CANCELLED, backend=backend, code="cancelled")


def failed(code, message, backend="builtin"):
    return CaptureResult(FAILED, backend=backend, code=code, message=message)


def from_image(image, backend="builtin"):
    """校验解码后的图片；无效结果不会进入附件流程。"""
    if image is None:
        return failed("invalid-image", "截图没有返回有效图片", backend)
    try:
        image.load()
        if image.width <= 0 or image.height <= 0:
            return failed("invalid-size", "截图尺寸无效", backend)
    except Exception as exc:
        return failed("decode-error", "截图无法解码：%s" % exc, backend)
    return CaptureResult(SUCCESS, image=image, backend=backend)


def from_png(path, backend="external"):
    """从后端临时 PNG 读取独立图片副本，并分类常见失败。"""
    if Image is None:
        return failed("pillow-missing", "未安装 Pillow，无法读取截图", backend)
    path = Path(path)
    if not path.is_file():
        return failed("missing-output", "截图后端未生成图片", backend)
    try:
        with Image.open(str(path)) as source:
            source.load()
            image = source.copy()
    except Exception as exc:
        return failed("decode-error", "截图文件无法解码：%s" % exc, backend)
    return from_image(image, backend)


@contextmanager
def temporary_png():
    """提供后端临时输出路径；成功、取消、异常退出均清理。"""
    handle = tempfile.NamedTemporaryFile(prefix="notecap-capture-", suffix=".png", delete=False)
    path = Path(handle.name)
    handle.close()
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
