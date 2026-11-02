# NoteCap

轻量、跨平台的速记与截图标注工具。通过全局快捷键唤起，将文字、截图和外部图片保存为标准 Markdown，便于后续检索、浏览和交给大模型处理。

## 功能

- 快速唤起与隐藏，唤醒后自动聚焦输入框。
- Markdown 速记、标签、历史记录和自定义保存目录。
- 框选截图、剪贴板图片粘贴、多图片插入与清单管理。
- 画笔、箭头、框选、颜色和线宽标注。
- 点击图片引用后预览或继续编辑对应图片。
- 浏览器打开当前 Markdown，内置常用语法速查。
- Windows、UOS / deepin ARM64，以及 Wayland / KWin 多屏适配。
- 未保存内容保护、保存失败恢复和跨平台自动化测试。

## 运行

需要 Python 3、Tkinter 和 Pillow。当前维护源码位于 `NOTECAP-7z/notecap-uos-arm64/`。

```bash
python -m pip install Pillow
python NOTECAP-7z/notecap-uos-arm64/notecap.py
```

Linux 如缺少 Tkinter，请通过系统包管理器安装。UOS ARM64 的完整安装、快捷键配置和 deb 打包方法见 [UOS 部署指南](DEPLOY-UOS.md)。

## 测试

```bash
python -m unittest discover -s tests -v
python -m py_compile NOTECAP-7z/notecap-uos-arm64/*.py
```

当前基线为 55 项测试。Linux 无图形显示环境时，可使用：

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

## 目录

- `NOTECAP-7z/notecap-uos-arm64/`：当前维护的应用源码与启动脚本。
- `tests/`：核心逻辑、UI、截图与打包测试。
- `docs/`：架构图、流程图和交互设计图。
- `DEPLOY-UOS.md`：UOS ARM64 部署说明。
- `CHANGELOG.md`：版本变更记录。

根目录的 `notecap.py` 为 Windows 历史版本；新功能和维护以 `NOTECAP-7z/notecap-uos-arm64/` 为准。
