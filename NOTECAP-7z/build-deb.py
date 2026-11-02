#!/usr/bin/env python3
"""
notecap deb 包构建脚本
用法: python3 build-deb.py
     如果系统 python3 < 3.8（海象运算符报错），直接跑：
       /home/admin1/.workbuddy/binaries/python/versions/3.13.12/bin/python3 build-deb.py

前置条件:
  1. dpkg-deb 可用 (sudo apt install dpkg-dev)
  2. 源文件在 notecap-uos-arm64/ 中

输出: dist/notecap_1.0.3-1_all.deb
"""

import hashlib
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(PROJECT_ROOT, "notecap-uos-arm64")
BUILD = os.path.join(PROJECT_ROOT, "build", "notecap-deb")
DIST = os.path.join(PROJECT_ROOT, "dist")

VERSION = "1.0.3-8"
DEB_NAME = f"notecap_{VERSION}_all.deb"


def run(cmd, cwd=None):
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ 失败: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def main():
    # 1. 检查 dpkg-deb
    print("[1/6] 检查工具…")
    if shutil.which("dpkg-deb") is None:
        print("  ✗ 未找到 dpkg-deb，请先安装: sudo apt install dpkg-dev")
        sys.exit(1)

    for source_name in ("notecap.py", "notecap_core.py", "notecap_capture.py"):
        if not os.path.isfile(os.path.join(SRC, source_name)):
            print(f"  ✗ 未找到源文件 {SRC}/{source_name}")
            sys.exit(1)

    # 2. 清理并创建目录结构
    print("[2/6] 准备包目录…")
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(os.path.join(BUILD, "DEBIAN"))
    os.makedirs(os.path.join(BUILD, "opt", "notecap"))
    os.makedirs(os.path.join(BUILD, "usr", "bin"))
    os.makedirs(os.path.join(BUILD, "usr", "share", "applications"))
    os.makedirs(DIST, exist_ok=True)

    # 3. 复制程序文件
    print("[3/6] 复制程序文件…")
    for f in ("notecap.py", "notecap_core.py", "notecap_capture.py", "notecap.sh", "NOTECAP-使用说明.md", "UOS-ARM-打包部署指南.md"):
        src = os.path.join(SRC, f)
        dst = os.path.join(BUILD, "opt", "notecap", f)
        shutil.copy2(src, dst)
        print(f"  {f}")

    os.chmod(os.path.join(BUILD, "opt", "notecap", "notecap.sh"), 0o755)

    # 创建 /usr/bin/notecap → 硬编码路径的启动脚本（dpkg-deb 有时不能正确处理符号链接）
    wrapper = os.path.join(BUILD, "usr", "bin", "notecap")
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\n")
        f.write("exec python3 /opt/notecap/notecap.py \"$@\"\n")
    os.chmod(wrapper, 0o755)
    print("  usr/bin/notecap (wrapper -> /opt/notecap/notecap.py)")

    # 4. 写入 control 文件
    print("[4/6] 写入包元数据…")
    control = os.path.join(BUILD, "DEBIAN", "control")
    with open(control, "w", encoding="utf-8") as f:
        f.write(
            "Package: notecap\n"
            f"Version: {VERSION}\n"
            "Section: utils\n"
            "Priority: optional\n"
            "Architecture: all\n"
            "Maintainer: Local Packager <local@localhost>\n"
            "Depends: python3 (>= 3.7), python3-tk, python3-pil, python3-pil.imagetk\n"
            "Recommends: xclip, fonts-noto-cjk, gnome-screenshot\n"
            "Description: Lightweight note and screenshot capture tool\n"
            " NoteCapture provides quick notes, clipboard images, screenshot\n"
            " annotation, and structured Markdown storage.\n"
        )
    os.chmod(control, 0o644)

    # 4.1 写入 postinst（安装后自动注册快捷键）
    postinst = os.path.join(BUILD, "DEBIAN", "postinst")
    with open(postinst, "w", encoding="utf-8") as f:
        f.write("""#!/bin/sh
set -e
# Register Ctrl+Shift+J global shortcut for notecap.
# 部分桌面（如无此 schema 的 UOS 变体）没有自定义快捷键 schema，跳过即可。
if command -v gsettings >/dev/null 2>&1 && \
   gsettings list-schemas 2>/dev/null | grep -qx "com.deepin.dde.keybinding.custom.mediakey"; then
  gsettings set com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle '<Control><Shift>J'
  gsettings set com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle-name '速记'
  gsettings set com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle-action '/opt/notecap/notecap.py --toggle'
fi
""")
    os.chmod(postinst, 0o755)

    # 4.2 写入 prerm（卸载时移除快捷键）
    prerm = os.path.join(BUILD, "DEBIAN", "prerm")
    with open(prerm, "w", encoding="utf-8") as f:
        f.write("""#!/bin/sh
set -e
# Remove global shortcut
if command -v gsettings >/dev/null 2>&1; then
  gsettings reset com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle 2>/dev/null || true
  gsettings reset com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle-name 2>/dev/null || true
  gsettings reset com.deepin.dde.keybinding.custom.mediakey custom-notecap-toggle-action 2>/dev/null || true
fi
""")
    os.chmod(prerm, 0o755)

    # 5. 写入 desktop 启动器
    desktop = os.path.join(BUILD, "usr", "share", "applications", "notecap.desktop")
    with open(desktop, "w", encoding="utf-8") as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=NoteCapture\n"
            "Name[zh_CN]=速记\n"
            "Comment=Quick notes and screenshot capture\n"
            "Comment[zh_CN]=快捷文字、图片和截图速记\n"
            "Exec=/opt/notecap/notecap.sh\n"
            "Icon=accessories-text-editor\n"
            "Terminal=false\n"
            "Categories=Utility;Office;\n"
        )
    os.chmod(desktop, 0o644)

    # 6. 构建 deb
    print("[5/6] 构建 deb…")
    deb_path = os.path.join(DIST, DEB_NAME)
    run(f"dpkg-deb --build {BUILD} {deb_path}", cwd=PROJECT_ROOT)

    # 验证
    print("[6/6] 验证…")
    info = run(f"dpkg-deb --info {deb_path}")
    for line in info.split("\n"):
        if "Architecture" in line or "Package" in line or "Version" in line:
            print(f"  {line.strip()}")

    # 跑 sha256
    sha = hashlib.sha256()
    with open(deb_path, "rb") as f:
        chunk = f.read(8192)
        while chunk:
            sha.update(chunk)
            chunk = f.read(8192)
    sha_hex = sha.hexdigest()

    sha_path = deb_path + ".sha256"
    with open(sha_path, "w", encoding="utf-8") as f:
        f.write(f"{sha_hex}  {DEB_NAME}\n")

    size_mb = os.path.getsize(deb_path) / (1024 * 1024)
    print(f"\n  ✅ 构建成功！")
    print(f"  文件: {deb_path}")
    print(f"  大小: {size_mb:.2f} MB")
    print(f"  SHA256: {sha_hex}")
    print(f"\n  安装: sudo apt install {deb_path}")
    print(f"  卸载: sudo apt remove notecap")


if __name__ == "__main__":
    main()