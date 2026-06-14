---
name: e-mail
description: "通过 IMAP/SMTP 连接邮箱，支持收发邮件、搜索、附件下载。支持标准 IMAP/SMTP 邮箱。触发关键词：邮件、邮箱、企业邮箱、发邮件、收件箱、email、inbox、send mail。"
description_zh: "通过 IMAP/SMTP 连接邮箱，支持收发邮件、搜索、附件下载。支持标准 IMAP/SMTP 邮箱。触发关键词：邮件、邮箱、企业邮箱、发邮件、收件箱、email、inbox。"
description_en: "Connect to email via IMAP/SMTP. Supports sending, receiving, searching, and downloading attachments. Works with standard IMAP/SMTP email providers."
version: "1.0.0"
---

# 邮箱收发技能（IMAP/SMTP）

通过 IMAP/SMTP 协议收发邮件，支持各类支持标准 IMAP/SMTP 协议的邮箱。

## 核心要求

1. **执行命令**前先切换到 `@skills` 所在的目录下
1. **发信**用 `node @skills/e-mail/scripts/smtp.bundle.js`
2. **收信/搜索/附件**用 `node @skills/e-mail/scripts/imap.bundle.js`
3. **凭证来源**
   - 从 `@skills/e-mail/.env` 读取：
     - EMAIL_USER
     - EMAIL_PASS
   - 若 `@skills/e-mail/.env` 不存在或字段缺失，则进入初始化配置流程
4. **JSON 格式输出**：所有命令输出标准 JSON，`success: true` 或 `success: false` + `message`。

## 前置条件

系统将自动读取 `@skills/e-mail/.env` 作为凭证来源。如果 `@skills/e-mail/.env` 不存在或字段缺失，将在首次使用时引导用户完成初始化。

## 初始化配置流程

1. 请用户在对话中发送：

    - 邮箱地址
    - IMAP/SMTP 授权码（非登录密码）

    **示例提示**：

    > 检测到邮箱未配置，请提供：
    > 1. 邮箱地址
    > 2. IMAP/SMTP 授权码（用于登录邮件服务器）
    > 
    > 我将为你完成本地配置（写入 @skills/e-mail/.env）

2. 当用户提供凭证后：

    - 写入 `@skills/e-mail/.env`
    - 格式如下：

      ```
      EMAIL_USER=xxx
      EMAIL_PASS=xxx
      ```
    - 如果 `@skills/e-mail/.env` 不存在 → 创建
    - 如果 `@skills/e-mail/.env` 存在 → 覆盖更新

3. 写入成功后提示：

    - “邮箱配置完成，可以开始使用邮件功能”

## 支持的邮箱

自动根据邮箱域名识别 IMAP/SMTP 服务器配置：

- 腾讯企业邮箱：chjgroup.com、chjchina.com、exmail.qq.com
- 网易系：163.com、126.com、yeah.net、188.com 及其 VIP 版本
- QQ/Foxmail：qq.com、foxmail.com
- Gmail：gmail.com
- Outlook：outlook.com、hotmail.com
- 其他：sina.com、sohu.com、139.com、aliyun.com

## 邮件分析与总结

通过 IMAP 获取邮件数据后，可对邮件进行深度分析与总结，用于生成邮件概览、重要事项提取、待办事项整理等。

### 触发条件

当用户请求以下内容时必须进入该流程：
- 总结邮件 / 邮件汇总 / email report
- 分析收件箱 / 过去X天邮件分析

### 执行流程

1. **意图澄清与预过滤**：
   - 优先通过参数进行精准查询，如遇到海量邮件，应主动询问用户是否增加筛选条件（如：`--unseen` 仅未读，限定发件人，或缩短 `--recent` 时间范围）。

2. **获取与保存数据（强制重定向写入本地）**：
   - **核心要求**：因为邮件数据量极大，**绝对禁止**直接在终端打印获取到的邮件详情。**必须**使用 Bash 的重定向符 `>` 将 JSON 结果写入本地工作空间的文件中。
   - **正确执行示例**：
     ```bash
     node @skills/e-mail/scripts/imap.bundle.js check --recent 7d --limit 20 > ./email_data.json
     ```
   - 写入文件后，再读取该 JSON 文件进行分析。读取数据时，必须剔除冗余的 HTML 标签和过长的历史回复引用，仅保留核心正文。

3. **聚类与分批（Chunk）处理**：
   - 优先将主题（Subject）相同的邮件聚合作为同一上下文。
   - 当邮件数量较多时，分批读取并处理，每批生成局部结构化摘要，不得遗漏关键信息。

4. **直接在对话中输出文本分析结果**：
   - 将所有的局部摘要进行二次梳理。
   - **强制输出格式**：最终的分析结果**必须直接在当前的对话框中以 Markdown 纯文本的形式回复给用户**，绝对不要将总结报告写成独立的文件（如 .txt 或 .md 文件）。
   - 直接回复的文本报告建议按以下结构输出：
     - 🔴 **紧急与重要**：需要立即关注或回复的邮件；
     - ✅ **行动项（Action Items）**：提取出的待办事项及截止时间；
     - 📎 **关键附件提醒**：提及重要附件的邮件（提醒用户可通过 download 命令下载）；
     - 📰 **常规信息与通知**：系统通知、简报等一笔带过即可。

## 发信命令（smtp.bundle.js）

### 发送邮件

```bash
node @skills/e-mail/scripts/smtp.bundle.js send \
  --to "recipient@example.com" \
  --subject "邮件主题" \
  --body "邮件正文"
```

#### 发送选项

| 参数 | 说明 |
|------|------|
| `--to` | **必填**，收件人地址 |
| `--subject` | **必填**，邮件主题 |
| `--body` | 正文内容 |
| `--html` | 标记为 HTML 格式（与 --body 配合） |
| `--body-file` | 从文件读取正文（.html 后缀自动识别为 HTML） |
| `--cc` | 抄送地址 |
| `--bcc` | 密送地址 |
| `--attach` | 附件路径（逗号分隔多个） |
| `--from` | 发件人地址（默认使用配置的邮箱） |

#### 示例

```bash
# 发送 HTML 邮件
node @skills/e-mail/scripts/smtp.bundle.js send \
  --to "colleague@company.com" \
  --subject "周报" \
  --html \
  --body "<h1>本周总结</h1><p>完成了 3 个任务</p>"

# 发送带附件的邮件
node @skills/e-mail/scripts/smtp.bundle.js send \
  --to "boss@company.com" \
  --subject "报告" \
  --body "请查收附件" \
  --attach "$HOME/Documents/report.pdf"

# 抄送密送
node @skills/e-mail/scripts/smtp.bundle.js send \
  --to "a@example.com" \
  --cc "b@example.com" \
  --bcc "c@example.com" \
  --subject "同步" \
  --body "请查收"
```

### 测试连接

```bash
node @skills/e-mail/scripts/smtp.bundle.js test
```

## 收信命令（imap.bundle.js）

### 查看收件箱

```bash
node @skills/e-mail/scripts/imap.bundle.js check \
  --limit 10 --recent 2h
```

| 参数 | 说明 |
|------|------|
| `--limit` | 返回邮件数量（默认 10） |
| `--recent` | 时间范围：`30m`（分钟）、`2h`（小时）、`7d`（天） |
| `--unseen` | 仅显示未读邮件 |
| `--mailbox` | 邮箱文件夹（默认 INBOX） |

### 搜索邮件

```bash
node @skills/e-mail/scripts/imap.bundle.js search \
  --subject "发票" --recent 7d --limit 20
```

| 参数 | 说明 |
|------|------|
| `--subject` | 按主题搜索 |
| `--from` | 按发件人搜索 |
| `--recent` | 时间范围 |
| `--unseen` | 仅未读 |
| `--seen` | 仅已读 |
| `--limit` | 结果数量（默认 20） |

### 获取邮件详情

```bash
node @skills/e-mail/scripts/imap.bundle.js fetch 12345
```

参数为邮件 UID（从 check/search 结果中获取）。

### 下载附件

```bash
node @skills/e-mail/scripts/imap.bundle.js download 12345 \
  --dir "$HOME/Downloads" --file "report.pdf"
```

| 参数 | 说明 |
|------|------|
| 第一个参数 | 邮件 UID |
| `--dir` | 保存目录（默认 ~/Downloads） |
| `--file` | 指定附件文件名（可选，不填则下载全部） |

### 标记已读/未读

```bash
node @skills/e-mail/scripts/imap.bundle.js mark-read 12345 12346
node @skills/e-mail/scripts/imap.bundle.js mark-unread 12345
```

### 列出邮箱文件夹

```bash
node @skills/e-mail/scripts/imap.bundle.js list-mailboxes
```

## 错误处理

- **凭证缺失**（error_code: 2）：引导用户进入初始化配置流程
- **认证失败**：提醒用户检查授权码是否正确、是否在网页端开启了 IMAP/SMTP 服务
- **连接超时**：网络波动或邮箱服务器限流，建议稍后重试
- **授权码过期/失效**：告知用户在邮箱网页端重新生成授权码，然后引导用户进入初始化配置流程

## 安全说明

- 所有连接使用 TLS 加密（IMAP:993 / SMTP:465）
- 凭证由 `@skills/e-mail/.env` 文件注入，禁止在输出中暴露完整授权码，禁止提交到 git
- 每次发送邮件前必须经过用户显式批准
- 附件读写受目录白名单限制（默认 ~/Downloads, ~/Documents）
