# notecap 仓库工作规范

## 代码与测试位置

- 源码（唯一维护线，UOS 版）：`NOTECAP-7z/notecap-uos-arm64/`（`notecap.py` / `notecap_core.py` / `notecap_capture.py`）
- 测试：`tests/`，unittest 数量以实际发现结果为准，已通过 sys.path 引导指向 UOS 版源码
- 打包：`python3 NOTECAP-7z/build-deb.py` → 产出 `NOTECAP-7z/dist/notecap_<版本>_all.deb`

## 工作流（必须遵守）

0. **版本验证规则（每次修复交付后必须执行）**：
   - 交付修复时随附验证命令，并以 `bash NOTECAP-7z/verify-install.sh` 输出为准：
     全 ✓ 且结论 ✅ 才算「运行最新包」；任何 ✗ 先处理、再交付。
   - 脚本检查四项：构建版本、安装版本、运行实例（启动时间 + 运行脚本 MD5 与仓库
     逐字节比对）、仓库同步状态。
   - 排查「改了没生效」第一步永远是跑这个脚本。单实例 socket 会把新启动转发给
     运行中的旧实例，肉眼无法分辨，必须以 MD5 比对为准。
0.1 **版本纪律**：发布级改动必须同步——`notecap.py` 的 `APP_VERSION`（唯一来源，
   标题栏/`--diag`/打包脚本都从这里取）、CHANGELOG 新增对应版本段；打包后跑
   verify-install.sh 对账，交付时附上其输出。
1. 修改代码后，本地验证通过才能推送：
   - `python3 -m unittest discover -s tests` —— 全部测试必须通过
   - `python3 -m py_compile NOTECAP-7z/notecap-uos-arm64/*.py`
2. 推送前先确认远端没有新提交：`git fetch origin`，再 `git push origin main`
3. **远端有更新时**：`git pull --rebase origin main` 合入本地 → 重跑全部测试联调通过 → 再推送
4. 不推送未跑过测试的代码；不用强制推送（no force push）

## 本机环境（UOS ARM64 开发机）

- Python 3.7.3 + tk 8.6 + Pillow 5.4.1，Wayland 会话（KWin）
- UI 测试需要桌面环境；无显示环境用 `xvfb-run -a python3 -m unittest discover -s tests`（CI 同款）
- git 凭据已配 store 路径限定（仅本仓库），push/pull 免输密码
- 真机验证：`notecap --diag` / `notecap --selftest`；注意直接 `python3 notecap.py` 会被单实例 socket 转发给运行中的实例
