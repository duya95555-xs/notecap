#!/bin/bash
# notecap 版本一致性自检 —— 「运行的是不是最新包」一键确认
# 检查四项：构建版本 / 安装版本 / 运行实例（启动时间 + 脚本 MD5 与仓库比对）/ 仓库同步
# 用法：bash NOTECAP-7z/verify-install.sh   全 ✓ 且结论 ✅ 才算运行最新包
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/NOTECAP-7z/notecap-uos-arm64"
fail=0

ok()  { printf "  ✓ %s\n" "$*"; }
bad() { printf "  ✗ %s\n" "$*"; fail=1; }

BUILD_VER=$(grep -oP '^APP_VERSION = "\K[^"]+' "$SRC/notecap.py" 2>/dev/null)
INST_VER=$(dpkg-query -W -f='${Version}' notecap 2>/dev/null)

echo "== 构建版本 =="
if [ -n "$BUILD_VER" ]; then ok "build-deb.py VERSION = $BUILD_VER"; else bad "build-deb.py 读不到版本号"; BUILD_VER="?"; fi
if ls "$REPO/NOTECAP-7z/dist/notecap_${BUILD_VER}_all.deb" >/dev/null 2>&1; then
    ok "安装包 dist/notecap_${BUILD_VER}_all.deb 已构建"
else
    bad "缺少 dist/notecap_${BUILD_VER}_all.deb（先跑 python3 NOTECAP-7z/build-deb.py）"
fi

echo "== 安装版本 =="
if [ -n "$INST_VER" ]; then
    if [ "$INST_VER" = "$BUILD_VER" ]; then ok "已安装 $INST_VER = 构建版本"
    else bad "已安装 $INST_VER ≠ 构建版本 $BUILD_VER（升级: sudo apt install $REPO/NOTECAP-7z/dist/notecap_${BUILD_VER}_all.deb）"; fi
else
    bad "系统未安装 notecap"
fi

echo "== 运行实例 =="
PIDS=$(pgrep -f "notecap\.py" || true)
if [ -z "$PIDS" ]; then
    bad "没有运行中的实例（notecap --toggle 启动）"
else
    for pid in $PIDS; do
        START=$(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')
        SCRIPT=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -oE '[^ ]*notecap\.py' | head -1)
        echo "  进程 $pid  启动于 ${START:-?}  脚本: ${SCRIPT:-（无路径）}"
        if [ -n "${SCRIPT:-}" ] && [ -f "$SCRIPT" ]; then
            A=$(md5sum "$SCRIPT" | cut -d' ' -f1)
            B=$(md5sum "$SRC/notecap.py" | cut -d' ' -f1)
            if [ "$A" = "$B" ]; then ok "运行中的脚本与仓库源码一致（最新代码）"
            else bad "运行中的脚本是旧代码！pkill -f notecap.py 后重新启动"; fi
        fi
    done
fi

echo "== 代码仓库 =="
cd "$REPO"
[ -z "$(git status --porcelain)" ] && ok "工作区干净" || bad "有未提交改动（先提交推送）"
timeout 15 git fetch -q origin 2>/dev/null || true
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo none)
if [ "$LOCAL" = "$REMOTE" ]; then ok "本地与 origin/main 同步（$(git log --oneline -1 | cut -d' ' -f1)）"
else bad "本地与 origin/main 不一致（先 git push/pull）"; fi

echo
if [ "$fail" -eq 0 ]; then echo "✅ 结论：运行中的就是最新包"
else echo "❌ 结论：存在不一致，按上面 ✗ 的提示处理后再验证"; exit 1; fi
