---
name: clean-up
description: 清除 Deskflow 控制 Ubuntu/X11 时卡住的键盘按下状态。用户说 clean up、键盘又卡了、Ctrl/Shift 像一直按住或请求释放残留按键时使用；不用于磁盘或文件清理。
---

# clean up

用于 Mac 等主机通过 Deskflow 控制 Ubuntu 接收端时，检测并释放 X11 记录的残留按键。调用本 skill 即授权一次检测和释放，不必再次请求确认。

1. 确认执行环境是出问题的 Ubuntu 接收端的图形会话。不要默认 SSH 所在机器就是目标，不要猜测 DISPLAY 或使用 sudo。目标不明确时先澄清。
2. 提示用户“请暂时松开所有键，我会检测并清除残留按键状态”。
3. 在 skill 目录运行 `python3 scripts/release_keys.py --release`。脚本输出按下键的 keycode、名称、释放列表和复查结果。仅查询时使用 `python3 scripts/release_keys.py`。
4. 根据输出说明是否成功释放，邀请用户试打字。没有检测到按下键时，不宣称已修复。释放后仍有按键时，报告未恢复，不循环释放；继续按用户需求检查 Deskflow 日志和连接。

脚本仅支持 Linux 原生 X11；Wayland 的 XWayland 查询不能代表整个桌面的输入状态，遇到 Wayland 或无法打开显示时停止此修复路径并说明原因。不得自动重启 Deskflow、终止进程、改映射、修改截图快捷键或安装依赖。

这里清除的是当前按下状态，不是 Caps Lock/Num Lock 等锁定状态，也不处理鼠标按钮。按键残留只证明接收端状态异常，不能单凭此结果断言 Deskflow 漏掉了松开事件。历史案例中曾同时检测到左右 Shift、Escape 和未命名 keycode；每次应重新查询，不硬编码这些键。
