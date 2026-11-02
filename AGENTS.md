# notecap 仓库工作规范

## 代码与测试位置

- 源码（唯一维护线，UOS 版）：`NOTECAP-7z/notecap-uos-arm64/`（`notecap.py` / `notecap_core.py` / `notecap_capture.py`）
- 测试：`tests/`，55 例 unittest，已通过 sys.path 引导指向 UOS 版源码
- 打包：`python3 NOTECAP-7z/build-deb.py` → 产出 `NOTECAP-7z/dist/notecap_<版本>_all.deb`

## 工作流（必须遵守）

1. 修改代码后，本地验证通过才能推送：
   - `python3 -m unittest discover -s tests` —— 55 例必须全部通过
   - `python3 -m py_compile NOTECAP-7z/notecap-uos-arm64/*.py`
2. 推送前先确认远端没有新提交：`git fetch origin`，再 `git push origin main`
3. **远端有更新时**：`git pull --rebase origin main` 合入本地 → 重跑全部测试联调通过 → 再推送
4. 不推送未跑过测试的代码；不用强制推送（no force push）

## 本机环境（UOS ARM64 开发机）

- Python 3.7.3 + tk 8.6 + Pillow 5.4.1，Wayland 会话（KWin）
- UI 测试需要桌面环境；无显示环境用 `xvfb-run -a python3 -m unittest discover -s tests`（CI 同款）
- git 凭据已配 store 路径限定（仅本仓库），push/pull 免输密码
- 真机验证：`notecap --diag` / `notecap --selftest`；注意直接 `python3 notecap.py` 会被单实例 socket 转发给运行中的实例
