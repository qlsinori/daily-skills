---
name: mac-windows-keyboard-deskflow
description: 将 Mac 键盘调整为 Windows 使用习惯，并处理 Deskflow 从 Mac 向 Windows 共享键鼠时的快捷键冲突。适用于 Fn/Control 对调、Ctrl 复制粘贴、Shift 中英文切换、Caps Lock 大写锁定及 Command/Win 组合键的配置和排错；也包含同类新机软件安装的可选流程。
---

# Mac / Windows 键盘与 Deskflow

目标是让用户实际按键在本机和远端都正确，而不是仅让配置文件通过解析。保留已正常的映射，每次针对失败项修改并备份。

## 先识别目标

- 读取系统版本、键盘设备、输入法、Karabiner 当前 profile、hidutil 映射和 Deskflow 角色/配置。
- 区分物理位置、键帽和逻辑键：Fn 与左 Control 对调后，用户的 Ctrl+C 应按原 Fn 位置。
- 询问跨设备方向和远端系统。本文的远端方案针对 Mac 服务端 → Windows 客户端；不能照搬到相反方向。
- 用户要求 Windows 习惯不代表同意对调 Control/Command。明确约定保留哪些原生快捷键，尤其 Command+Tab。
- 应用安装只有在用户请求时才执行，见 [可选软件安装](references/software-setup.md)。

## 配置原则

1. 对修饰键和组合键使用单一主要映射工具。使用 Karabiner 后，把既有 hidutil Fn/Control 对调迁移到内置键盘的 simple modifications，停用自己创建的重复登录任务；保留其他映射。
2. Ctrl+C/V/X/A/Z/S/F 等在 Mac 上转换为对应 Command 组合。仅映射指定组合，避免整个 Control 改成 Command。Ctrl+Y 对应 Command+Shift+Z。
3. 旧 NSUserKeyEquivalents 可能与底层转换冲突；备份后只清理本次流程引入的条目，不能无条件删除用户全部菜单快捷键。
4. 单按左右 Shift 切换输入法；按住与字母、符号、组合键连用时保持 Shift。对中文输入法优先发送系统已启用的输入法切换快捷键，不假设 select_input_source 一定可靠。
5. Caps Lock 只负责大写。先检查系统输入法的 Caps Lock 语言切换选项；配置值显示关闭不等于行为已刷新。若仍切换语言，要求描述具体表现并核对实际界面，不反复写猜测的 defaults 键。
6. Command 只按约定映射为 Win 对应操作。默认保留 Command+Tab 应用切换。Command+D 先区分临时显示桌面和持久收起窗口。Command+Mission Control 只是临时露出桌面，点击可能恢复；若用户要求点击桌面不回弹，使用隐藏其他应用并收起 Finder 窗口的方案，说明通过 Command+Tab 返回应用。不要把裸 F11 当作可靠实现。

具体配置结构、Deskflow 进入/离开回调及故障记录见 [配置与排错](references/keyboard-workflow.md)。

## 本机与远端必须分开

Mac 需要 Ctrl+C → Command+C；Windows 需要原始 Ctrl+C。统一转换后再发送，会让 Windows 收到错误的 Super/Win+C。

用 Deskflow 的进入/离开命令设置 Karabiner 变量，例如 deskflow_remote。仅在本机启用 Mac 专用复杂映射；远端透传 Ctrl、Shift、Caps Lock、Command/Win。Fn/Control 的物理位置对调通常两边都保留。不要同时再给 Windows 做 Ctrl/Super 对调，否则容易重复转换。

进入/离开回调可能乱序完成，使用带文件锁且以最新 Deskflow 日志判定模式的同步脚本，见参考文档。回调需要验证往返各一次；退出/重连后也要检查变量没有停留在远端。遇到 Deskflow 不允许自动退出，不强杀来绕过用户取消；要求正常重启后继续验证。

## 验证与交付

分别记录：文件校验通过、服务就绪、用户实按确认。前两项不能代替第三项。

- Mac 输入框：全选、复制、粘贴、剪切、撤销；不要用用户已有正文做破坏性测试。
- Shift：轻按切换；Shift+字母不意外切换；大写锁定时仍能操作。
- Caps Lock：测试灯、连续大写和再次关闭，并确认不是切换输入法。
- Command+Tab：切换应用；Command+D：按约定验证临时切换或持久桌面；持久方案需验证点击桌面不回弹及 Command+Tab 返回应用。
- Windows：鼠标跨屏后 Ctrl+C/V、Win+D/E、大小写和输入法；回 Mac 后再次测试。

macOS 驱动扩展/输入监控可能需要用户在系统界面批准。解释实际缺失权限，不能声称已代为开启。必要时请用户提供当前设置截图以定位控件。

新技能和配置可以本地准备；上传 Git 仅在当前请求授权时进行。发布内容必须去除用户名、机器名、IP、证书、个人配置和凭据。
