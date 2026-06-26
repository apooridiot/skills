---
name: wechat-clawbot-notify
description: "Send notification messages and files to the user's WeChat via ClawBot (iLink API). Supports text messages, PDFs, images, and other file attachments. Use when automation tasks complete and need to notify the user, or when the user asks to send a message/file to their WeChat. Triggers on: 'notify me on WeChat', 'send to my WeChat', 'push result to WeChat', '发微信通知', '推送到微信', '通知我', '发文件到微信', 'PDF发到微信'."
description_zh: "通过微信 ClawBot 发送通知消息和文件给用户，支持文本消息及PDF/图片等附件"
description_en: "Send notification messages and files to user's WeChat via ClawBot"
version: 1.3.0
allowed-tools: Bash,Read
compatibility: macOS / Windows / Linux. Requires Python 3 + cryptography. Reads config from WorkBuddy settings.json.
metadata:
  version: "1.3.0"
  openclaw:
    emoji: "\U0001F4AC"
    requires:
      bins:
        - python
        - cryptography
---

# WeChat ClawBot Notify

通过微信 ClawBot iLink API 发送文本消息和文件给用户。

> **平台说明**：统一使用 `python` 执行脚本。macOS/Linux/Bash 使用 `$SKILL_DIR/scripts/...`；Windows PowerShell 使用 `$env:SKILL_DIR\scripts\...`。要求 `python` 指向 Python 3。

## 初始化检查（必须优先执行）

**使用任何命令前，先执行 `status` 检查配置和 token 状态。不要只根据 `.token_cache.json` 是否存在判断技能已就绪；该文件可能只有 `get_updates_buf` 游标，没有可发送消息的 `context_token`。**

### 第 1 步：检查 ClawBot 配置

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" status
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" status
```

- **输出 `Ready: True` 且 `Token:` 显示 token 前缀** → 技能已就绪，直接跳到 [发送消息](#发送消息)。
- **输出 `Ready: False` 或 `Token: Not cached`** → 进入第 2 步。
- **报错** → ClawBot 未配置。告诉用户："请先在 WorkBuddy 设置中连接你的微信 ClawBot 通道。" 到此停止。

### 第 2 步：获取 context_token

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" refresh
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" refresh
```

- **成功**（输出 "Token refreshed successfully"）→ 进入第 3 步。
- **失败**（输出 "No messages with context_token found"）→ 告诉用户："请打开微信，给你的 ClawBot 发一条消息，然后告诉我继续。" **等待用户确认后**，重试本步骤。

### 第 3 步：配置自动通知

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/inject_soul.py"
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\inject_soul.py"
```

将自动通知指令写入 `~/.workbuddy/SOUL.md`，后续自动化任务完成后会自动使用本技能通知用户。幂等操作，可重复执行。

### 第 4 步：发送验证消息

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" send "微信 ClawBot 通知技能配置完成！后续自动化任务完成后会自动通知你的微信。"
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" send "微信 ClawBot 通知技能配置完成！后续自动化任务完成后会自动通知你的微信。"
```

- **成功** → 告诉用户："配置完成！验证消息已发送到你的微信，后续自动化任务会自动通知你。"
- **失败** → 告诉用户："配置基本完成，但验证消息发送失败。稍后可以尝试执行 refresh 刷新 token。"

---

## 发送消息

### 发送文本

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" send "消息内容"
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" send "消息内容"
```

### 发送文件（PDF/图片等）

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" sendfile "/path/to/file.pdf"
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" sendfile "C:\path\to\file.pdf"
```

> **注意**：文件发送涉及 4 步流程（AES-128-ECB 加密 → getuploadurl → 上传CDN → sendmessage），耗时较长（大型文件可能需 60 秒以上）。sendfile 命令会自动在 token 过期时尝试刷新重试。
>
> **已知踩坑**：发送成功后微信显示文件卡片但下载失败，通常是 `aes_key` 编码问题。正确的编码方式是 `base64(aeskey_hex_string.ascii_bytes)`，即先将 hex 密钥字符串本身作为 ASCII 字节取 base64，而非对原始 16 字节密钥取 base64。

## 命令参考

| 命令 | 说明 |
|------|------|
| `send` | 发送文本消息 |
| `sendfile` | 发送文件（PDF/图片等） |
| `status` | 查看配置和 token 状态 |
| `refresh` | 刷新缓存的 token |

### 查看状态

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" status
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" status
```

### 刷新 token

发送失败时，刷新缓存的 token：

macOS / Linux / Bash:
```bash
python "$SKILL_DIR/scripts/send_wechat.py" refresh
```

Windows PowerShell:
```powershell
python "$env:SKILL_DIR\scripts\send_wechat.py" refresh
```

## 故障排查

| 问题 | 解决方法 |
|---|---|
| `.token_cache.json` 不存在 | 按上面的初始化步骤执行 |
| "No cached context_token" | 用户给 ClawBot 发一条消息，然后执行 `refresh` |
| "getupdates returned ret=-14" | 旧缓存 cursor 或旧 ClawBot 配置失效；脚本会自动丢弃 cursor 重试。仍失败时，让用户给 ClawBot 再发一条消息后执行 `refresh` |
| 发送静默失败 | 执行 `refresh` 获取新的 token |
| "HTTP 401" | 检查 WorkBuddy 设置中的 botToken |
| 文件发送显示卡片但下载失败 | `aes_key` 编码问题：应为 base64(hex_string.ascii_bytes)，已修复到最新代码中。确认脚本是最新版本 |
| 文件发送卡在上传步骤 | CDN 上传环节响应头缺少 `x-encrypted-param`。检查 getuploadurl 返回的 `upload_param` 和 `filekey` 是否一致 |
| 脚本报 `ModuleNotFoundError: cryptography` | 执行 `pip install cryptography` 安装依赖 |

## 工作原理

1. **配置**：从 WorkBuddy settings 读取 `claw.channels.weixinClawBot`（botToken、userId、baseUrl）
2. **Token**：调用 `/ilink/bot/getupdates` 从最近的消息中获取 `context_token`，缓存到本地
3. **发送文本**：使用缓存的 token 向 `/ilink/bot/sendmessage` 发送 `type:1` 文本消息
4. **发送文件**：4 步流程 — ① AES-128-ECB 加密文件内容 ② 调用 `/ilink/bot/getuploadurl` 获取 CDN 上传地址 ③ POST 加密数据到 WeChat CDN，从响应头提取 `x-encrypted-param` ④ 发送 `type:4` 文件消息（含 `file_item.media.encrypt_query_param` + `aes_key` base64 编码）
5. **重试**：发送失败时自动刷新 token 并重试一次
6. **日志**：所有操作记录到 `logs/send_wechat.log`
