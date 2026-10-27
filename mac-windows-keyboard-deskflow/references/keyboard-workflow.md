# 配置与排错参考

## 观察现状

常用只读检查：

```sh
sw_vers
hidutil list
hidutil property --get UserKeyMapping
defaults read com.apple.HIToolbox AppleEnabledInputSources
defaults read -g NSUserKeyEquivalents
systemextensionsctl list
```

Karabiner CLI 常见路径：
`/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli`

使用 `--show-current-profile-name`、`--list-connected-devices`、`--show-settings-window-guidance` 检查选中配置、设备和权限。支持的参数以本机 `--help` 为准。配置默认在 `~/.config/karabiner/karabiner.json`。读取后合并已有 profile/rules/devices，不覆盖整份用户配置。

## 映射示例

以下是规则片段，不是整份可覆盖的配置。设备限定使用实测 identifiers，不硬编码其他电脑的设备 ID。

内置键盘 simple modifications：

```json
[
  {"from":{"key_code":"fn"},"to":[{"key_code":"left_control"}]},
  {"from":{"key_code":"left_control"},"to":[{"key_code":"fn"}]}
]
```

本机 Ctrl+C（其他按键按需增加；允许 Shift 和 Caps Lock）：

```json
{
  "type":"basic",
  "from":{"key_code":"c","modifiers":{"mandatory":["control"],"optional":["shift","caps_lock"]}},
  "to":[{"key_code":"c","modifiers":["left_command"]}],
  "conditions":[{"type":"variable_unless","name":"deskflow_remote","value":1}]
}
```

轻按 Shift；示例假设系统 Control+Space 已启用为输入法切换。为 right_shift 添加对应规则：

```json
{
  "type":"basic",
  "from":{"key_code":"left_shift","modifiers":{"optional":["caps_lock"]}},
  "to":[{"key_code":"left_shift"}],
  "to_if_alone":[{"key_code":"spacebar","modifiers":["left_control"]}],
  "parameters":{"basic.to_if_alone_timeout_milliseconds":350},
  "conditions":[{"type":"variable_unless","name":"deskflow_remote","value":1}]
}
```

临时显示桌面的 Command+D 输出（不满足点击桌面后仍保持桌面的要求）：

```json
{"apple_vendor_keyboard_key_code":"mission_control","modifiers":["left_command"]}
```

这是 Apple 文档中的临时显示桌面组合，点击可能恢复窗口，并非 Windows 风格的持久收起窗口。不要再创建 Command+Tab → Mission Control 规则，除非用户明确要求改变应用切换习惯。

## 持久显示桌面

本案例用户明确拒绝点击后恢复窗口的临时效果。采用以下 AppleScript 隐藏其他普通应用并收起 Finder 窗口，不退出应用、不关闭文档：

```applescript
tell application "Finder"
    set collapsed of every Finder window to true
    activate
end tell
tell application "System Events"
    set visible of every application process whose background only is false and name is not "Finder" to false
end tell
```

将脚本保存到用户配置目录，Command+D 的 `to` 使用 `shell_command` 调用 osascript，保留本机条件。检查必要的自动化授权，实际执行并确认普通应用隐藏、Finder 窗口 collapsed。不能因命令行执行成功就假设 Karabiner 触发上下文的授权也通过。

此方案不是逐窗口最小化，也不提供再次 Command+D 恢复全部窗口。用 Command+Tab 返回应用；Finder 最小化窗口从 Dock 恢复。若用户明确需要可逆 Win+D 切换，另行设计并验证可见应用和窗口状态的保存/恢复，不能声称已有该功能。

## Deskflow 的跨屏状态


先找真实配置路径；macOS 常见为 `~/Library/Deskflow/Deskflow.conf`。确认当前版本支持 `[core]` 的四个字段，并保留原有回调。

```ini
[core]
enableEnterCommand=true
enterCommand=/bin/sh /ABSOLUTE/PATH/deskflow-local.sh
enableExitCommand=true
exitCommand=/bin/sh /ABSOLUTE/PATH/deskflow-remote.sh
```

进入/离开回调共用 [deskflow-sync-mode.rb](../scripts/deskflow-sync-mode.rb)。将脚本复制到用户配置目录，两个 shell wrapper 分别执行：

```sh
# local wrapper
exec /usr/bin/ruby "$HOME/.config/karabiner/deskflow-sync-mode.rb" local
# remote wrapper（放在另一个文件中）
exec /usr/bin/ruby "$HOME/.config/karabiner/deskflow-sync-mode.rb" remote
```

脚本默认读取 `~/Library/Deskflow/deskflow-diagnostics.log` 的最后 64 KiB；先确认 Deskflow `[log]` 配置 `toFile=true`、`level=Info` 和该绝对文件路径。若部署路径不同，需要同时调整脚本和 Deskflow。只收集连接级日志，不采集输入字符。

**不要让两个回调各自无条件写 0/1。** 快速跨屏时，exit 和 enter 命令可能乱序完成：最新日志已 entering，但较早的 exit 最后写入 remote，导致本机 Shift/Ctrl 映射失效。脚本通过文件锁串行化回调，再读取最新 entering/leaving 记录决定状态；Karabiner 更新成功后才写状态文件。日志缺失或无有效记录时退回回调参数，此降级模式不保证消除乱序，需检查日志配置。文件锁只能协调使用同一脚本的调用，不覆盖其他程序直接修改变量的情况。

2026-10-27 实测一次离开/返回仅相隔约 20 ms，日志为 entering，状态文件却为 remote。改用此脚本并同步本机模式后，用户确认 Shift 恢复。验证包含双向乱序回调和 8 个并发回调，均按最新日志状态收敛。此修复不等同于修复远端 Ctrl 卡住。

对所有仅适用于 Mac 的复杂规则增加 variable_unless 条件，包括 Ctrl 转 Command、Shift 输入法切换和 Command 的 Win 风格动作。不要给物理 Fn/Control simple modifications 加本机限制。

应用可能在退出时重新保存设置。备份，正常退出，写入，重启并检查文件是否保持，是优先方式；若不能退出，保存配置后要求用户正常重开，并复查最终文件与回调。

## Caps Lock 专项

macOS 26 官方路径：系统设置 → 键盘 → 文字输入 → 编辑；选项名称可能为“使用大写锁定键切换‘ABC’输入法”，ABC 会随上次拉丁输入法变化。部分键盘键帽标为“中/英”。

区分：

- 仍切换中英文：核对系统界面开关；若显示已关，可在界面开再关并完成，让运行中的设置刷新。找不到就看截图，别继续猜名称。
- 灯不亮、短按无反应：检查实际事件和 Caps Lock 防误触延时；Karabiner 的 caps_lock 输出可使用 hold_down_milliseconds: 200，不能据此推断语言切换已禁用。
- 灯亮但不是大写：检查输入法行为与实际输出；不能把切到 ABC 伪装成大写锁定。

历史尝试过 TISRomanSwitchState=0 和 AppleTISAllowCapsLockLayoutSwitching=false；只凭这些值并未解决用户实际问题。不要将它们写成已验证的一键修复，也不要通过重启/注销用户会话强制刷新未保存的工作。

## 本次案例的证据边界

- 菜单快捷键方案在浏览器不可靠，迁移到 Karabiner 的按键组合转换后，本机 Ctrl 操作由用户确认正常。
- Mac 专用映射无条件应用时破坏 Windows 远端复制粘贴；加入 Deskflow 状态回调并正常重开后，用户确认远端正常。
- Caps Lock 经系统设置排查后用户反馈成功；没有捕获最终开关状态变化，不能声称某条 defaults 命令是已验证根因修复。
- 用户要求恢复 Command+Tab，删除其 Mission Control 重映射即可保留原生应用切换。
- 裸 F11 的 Command+D 方案失败；Command+Mission Control 能露出桌面，但用户指出点击后恢复窗口，不符合预期。已改成隐藏其他应用并收起 Finder 窗口，脚本执行成功；快捷键实按和桌面点击效果仍需用户确认。

## 远端修饰键偶发卡住

本案例另有一次 Windows 端像 Ctrl 一直按住的现象，随后自行恢复，根因未确认。不要将其直接归因于键盘映射或声称已修复 Deskflow 缺陷。

先询问可复现表现，或在 Windows 屏幕键盘查看松开物理键后哪个修饰键仍高亮。检查跨屏回调状态、两端版本、锁屏/唤醒时机和修饰键按下/松开是否跨越屏幕切换。恢复操作可尝试在远端按下再松开对应键，必要时用 Windows 本机键盘释放，最后才正常断开重连。现象消失后避免无依据修改已正常的映射。

日志优先使用连接级 Info；若需要按键级日志，限定受控测试，不记录用户日常输入。未经核实的网上相似 issue 只能作为线索。

## 官方资料


- [Deskflow 配置及 enter/exit commands](https://github.com/deskflow/deskflow/blob/master/docs/Configuration.md)
- [Karabiner 单按键规则](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to-if-alone/)
- [中文输入法与 select_input_source 限制](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to/select-input-source/)
- [macOS 26 输入法切换设置](https://support.apple.com/zh-cn/guide/chinese-input-method/cim119a8d473/104/mac/26)
- [Apple 显示桌面快捷键](https://support.apple.com/guide/mac-help/view-open-windows-spaces-mission-control-mh35798/mac)
