# zhihu-cli

[![PyPI version](https://img.shields.io/pypi/v/pyzhihu-cli?label=PyPI)](https://pypi.org/project/pyzhihu-cli/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pyzhihu-cli)](https://pypi.org/project/pyzhihu-cli/)
[![PyPI - License](https://img.shields.io/pypi/l/pyzhihu-cli)](https://pypi.org/project/pyzhihu-cli/)
[![ClawHub](https://img.shields.io/badge/ClawHub-install-E65100)](https://clawhub.ai/BAIGUANGMEI/pyzhihu-cli)

知乎命令行工具 — 在终端搜索问题、查看回答、发布提问、发布想法、发布文章(图文混合，富文本支持)、浏览热榜

## 功能

- **认证** — Web 会话二维码/Cookie 登录，或官方开放平台 Access Secret 登录
- **搜索** — 按关键词搜索问题、回答、文章
- **热榜** — 查看知乎热榜及热门回答
- **问题** — 查看问题详情及回答
- **回答** — 查看回答详情及评论（支持 `--comments` 显示评论，`--limit` 控制数量，默认全部）
- **发布** — 发布提问、发布想法、发布文章（图文混合，富文本支持）
- **用户** — 查看用户资料、回答、文章、关注/粉丝
- **推荐** — 获取首页推荐内容（`feed` 显示列表，`feeds` 显示内容+评论）
- **话题** — 查看话题详情及热门问题
- **互动** — 赞同/取消赞同回答，关注/取消关注问题
- **收藏** — 查看收藏夹列表
- **通知** — 查看通知消息
- **JSON 输出** — 所有数据命令支持 `--json`
- **安全执行** — 全局 `--readonly` / `--read-only` 阻止发布、互动和删除
- **官方 CLI** — 透传官方知乎 CLI，使用官方 API 能力并明确提示当前后端与权限范围
- **终端工作台** — 默认进入全屏控制台，提供侧栏导航、工作区和命令输入；普通子命令 CLI 仍然保留
- **降低风控/反爬** — 全局统一 Chrome 浏览器指纹（`User-Agent` + `sec-ch-ua` + `sec-ch-ua-platform` 一致，版本号集中管理于 `config.CHROME_VERSION`）；登录与写操作带 CSRF（`_xsrf` / `x-xsrftoken`）。

## 命令一览

| 分类       | 命令                                     | 说明                           |
|------------|------------------------------------------|--------------------------------|
| Auth       | login, logout, status, whoami            | Web 会话登录、官方 API 登录、退出、状态检查、查看资料 |
| Official   | api                                      | 调用官方知乎开放平台 CLI |
| Read       | search, hot, question, answer            | 搜索、热榜、问题详情、回答详情 |
| Users      | user, user-answers, user-articles        | 查看资料、回答列表、文章列表   |
| Social     | followers, following                     | 查看粉丝、关注列表             |
| Feed       | feed, feeds, topic                      | 推荐 Feed、推荐+评论、话题详情 |
| Interact   | vote, follow-question                    | 赞同回答、关注问题             |
| Create     | ask, pin, article                        | 发布提问、发布想法、发布文章（图文混合，富文本支持）     |
| Delete     | delete-question, delete-pin, delete-article | 删除自己的提问、想法、文章（需确认，可 -y 跳过） |
| Safety     | --readonly, --read-only                  | 阻止发布、互动和删除，不发起知乎请求       |
| Other      | collections, notifications               | 收藏夹、通知                   |

> 所有数据命令支持 `--json` 输出。

## 安装

需要 Python 3.10+。

```bash
# 推荐：使用 uv
uv tool install pyzhihu-cli

# 或使用 pipx
pipx install pyzhihu-cli

# 从源码安装（开发用）
pip install -e .
```

二维码登录使用知乎 API（`/api/v3/account/api/login/qrcode`），**无需安装 Playwright**，仅需本工具依赖的 `requests` 与 `qrcode`。

### 两种后端与权限范围

本工具同时保留两套认证后端。每次调用官方 API 命令时，终端会在 stderr 提示 `Backend: Official API`；结构化结果仍写入 stdout，便于管道处理。

| 后端 | 登录方式 | 可用范围 | 不包含 |
|---|---|---|---|
| Web 会话 | `zhihu login --qrcode` / `zhihu login --cookie ...` | 搜索、浏览、草稿、互动，以及发布提问/想法/文章 | 依赖知乎 Web 会话 Cookie |
| 官方 API | `zhihu login --api` | 官方 CLI 暴露的公开搜索、本人用户数据、知识库和额度查询 | 不发布 Web 内容、不读取私人草稿；官方 API 权限以账号和接口授权为准 |

官方 API 登录只把 Access Secret 交给官方 CLI，通过隐藏输入读取，不会放入命令行参数。官方 CLI 自己负责保存凭证。

```bash
# Web 会话：草稿和发布功能使用这一后端
zhihu login --qrcode
zhihu drafts
zhihu article "标题" "正文"

# 官方 API：官方 CLI 的命令通过 api 透传
zhihu login --api
zhihu api capabilities
zhihu api search zhihu --query "量子引力"
zhihu api me contents --type all --limit 20
zhihu api knowledge search --query "资料" --scope personal --limit 10
zhihu api quota --api-id user_data
```

`zhihu api` 支持官方 CLI 的完整子命令和参数，不在本项目中重复封装。运行 `zhihu api` 可查看使用提示，运行 `zhihu api <command> --help` 可查看官方帮助。官方 CLI 未安装或路径异常时，终端会给出明确错误。

官方 API 的写操作默认仍可透传；使用全局只读模式时，知识库上传会被本工具拦截：

```bash
zhihu --readonly api knowledge search --query "资料"
zhihu --readonly api knowledge upload --file ./notes.md  # 被拦截
```

### 重叠能力的后端选择

搜索和热榜等重叠能力默认遵循“设置的优先级 → Session → 官方 API”。两者都已配置时默认使用 Session；可以在单次调用中用 `--session` 或 `--api` 覆盖，也可以持久化设置：

```bash
zhihu config show
zhihu config set priority session   # 默认值
zhihu config set priority api
zhihu config set language zh        # 首次配置提示默认中文，也支持 en

zhihu search "Python" --session
zhihu search "Python" --api
zhihu hot --api
```

官方 API 也提供独立入口。下面三种方式等价地表达“优先/调用官方 API”：

```bash
# 方式一：独立入口，所有参数直接交给官方 CLI
zhihu-api capabilities
zhihu-api search zhihu --query "Python"

# 方式二：本次调用强制 API（全局或重叠命令后置参数）
zhihu --api search "Python"
zhihu search "Python" --api

# 方式三：设置默认路由，之后重叠命令优先 API
zhihu config set priority api
zhihu search "Python"
```

单次 `--session` / `--api` 的优先级高于设置；`zhihu-api` 始终只使用官方 API，不参与 Session 回退。

两种后端都未配置时，命令会显示中文和英文的首次配置提示，并给出 `login --qrcode` 与 `login --api` 两条路径。

### 多账号

Session 和官方 API 都支持保存多套命名账号。Session Cookie 保存在本地 `accounts.json`（权限 `0600`），官方 API Access Secret 保存在 macOS Keychain，不写入配置文件。

```bash
# 分别登录多个 Web Session 账号
zhihu login --account personal --qrcode
zhihu login --account work --cookie "z_c0=...; _xsrf=...; d_c0=..."

# 分别登录多个官方 API 账号（Access Secret 隐藏输入）
zhihu login --api --account personal
zhihu login --api --account research

# 查看、切换和删除账号
zhihu account list
zhihu account use work --backend session
zhihu account use research --backend api
zhihu account remove work --backend session

# 只对本次调用使用指定账号，不改变默认账号
zhihu --account personal search "Python"
zhihu --account research api me contents --type all --limit 20
```

`account` 和 `accounts` 是同一个命令入口。TUI 中会显示当前 Session/API 账号，并可通过 `:` 执行 `account list` 或 `account use <name> --backend <session|api>`；也可以直接运行 `zhihu-tui --account personal` 将某个账号固定到本次工作台会话。

### 内置帮助与操作引导

无需打开 README 即可查看常用流程；`guidance` 和 `guide` 是同一个入口：

```bash
zhihu guidance                 # 快速开始与可用主题
zhihu guidance accounts        # 多账号登录、切换、删除和单次覆盖
zhihu guidance backends        # Session / Official API 路由
zhihu guidance tui             # 工作台和快捷键
zhihu guidance safety          # 只读模式与凭据存储
zhihu guide 账号               # 支持中文主题别名
```

TUI 左侧新增“帮助”工作区，选中后按 `Enter` 会在中央输出区显示快速开始指南。

## AI Agent Skill

本项目提供了 AI Agent Skill，可通过 [OpenClaw](https://openclaw.ai) 下载使用：

```
clawhub install pyzhihu-cli
```

安装后，AI Agent 可自动获取 zhihu-cli 的完整使用说明、命令参考、项目架构和开发指南。

**扫码登录与 Agent**：执行 `zhihu login --qrcode` 时，二维码会保存为 **`~/.zhihu-cli/login_qrcode.png`**（Windows 为 `%USERPROFILE%\.zhihu-cli\login_qrcode.png`）。Agent 可读取该图片并发送给用户，由用户在知乎 App 中扫码完成登录。

## 使用

### 终端界面

直接运行 `zhihu` 会进入全屏终端工作台：左侧切换首页、推荐、热榜、搜索、写作和草稿，底部使用 `:` 输入任意现有 CLI 命令，`Enter` 执行，`q` 退出。工作台只负责交互和导航，真实请求仍由现有命令与 Session/API 路由完成。

```bash
zhihu-tui             # 全屏工作台（交互式终端）
zhihu                 # 普通 CLI 首页/兼容输出
zhihu --classic       # 单次输出兼容模式，适合日志、管道和不支持 curses 的终端
zhihu feed            # 普通 CLI 子命令，直接输出并可继续使用全部参数
zhihu search "Python" --api
```

工作台快捷键：`↑/↓` 或 `j/k` 导航，`1`–`6` 切换工作区，`:` 打开命令输入，`Enter` 执行当前命令，`q` 或 `Esc` 退出。通过 SSH、IDE 内置终端或管道运行时若无法启用全屏模式，会自动降级到兼容首页。

草稿工作区只在终端显示草稿标题，不在终端编辑或渲染 Markdown。选择编号后可将内容写入本地 Markdown 副本，并用系统默认 Markdown 应用打开：

```bash
zhihu drafts
zhihu drafts --open 1
```

### 登录

Web 会话支持 **二维码扫码** 或 **手动粘贴 Cookie**；官方开放平台支持 **Access Secret**。

```bash
# 二维码扫码登录（推荐）；二维码会保存为 ~/.zhihu-cli/login_qrcode.png，供 AI Agent 发送给用户扫码
zhihu login --qrcode

# 手动粘贴 Cookie（至少包含 z_c0、_xsrf、d_c0）
zhihu login --cookie "z_c0=xxx; _xsrf=yyy; d_c0=zzz"

# 官方开放平台 Access Secret（输入时不回显）
zhihu login --api

# 检查登录状态
zhihu status

# 查看个人资料
zhihu whoami
zhihu whoami --json

# 退出登录
zhihu logout
```

### 只读模式

在命令前加 `--readonly`（或同义参数 `--read-only`），即可阻止所有发布、互动和删除命令。拦截发生在读取登录态和创建客户端之前，不会向知乎发起请求；登录、状态检查和查询命令仍可使用。

```bash
# 查询命令照常执行
zhihu --readonly search "Python"
zhihu --read-only question 12345678

# 以下命令会被拦截，不会发布或删除
zhihu --readonly pin "不会发布"
zhihu --readonly delete-pin 12345678 -y
```

### 搜索

```bash
zhihu search "Python 学习"
zhihu search "机器学习" --type topic
zhihu search "张三" --type people
zhihu search "Python" --json
```

### 热榜

```bash
zhihu hot                          # 全部热榜 + 各3条回答
zhihu hot -l 10                    # 10 条热榜
zhihu hot -a 5                     # 每条 5 条回答
zhihu hot -a 0                     # 仅标题，不带回答
zhihu hot --json
```

### 问题

```bash
# 查看问题详情
zhihu question <question_id>

# 包含回答
zhihu question <question_id> --answers

# 限制回答数量
zhihu question <question_id> --answers --limit 10
```

### 回答

```bash
# 查看回答详情
zhihu answer <answer_id>

# 包含评论（默认显示全部）
zhihu answer <answer_id> --comments
zhihu answer <answer_id> -c

# 限制评论数量
zhihu answer <answer_id> -c -l 5
```

### 用户

```bash
# 查看用户资料（使用 URL Token）
zhihu user <url_token>

# 查看用户回答
zhihu user-answers <url_token>
zhihu user-answers <url_token> --sort voteups

# 查看用户文章
zhihu user-articles <url_token>

# 粉丝 / 关注
zhihu followers <url_token>
zhihu following <url_token>
```

### 推荐 & 话题

```bash
# 推荐列表（仅 ID、类型、标题、作者）
zhihu feed
zhihu feed --limit 5

# 推荐 + 回答内容 + 评论
zhihu feeds
zhihu feeds -l 3          # 3 条推荐
zhihu feeds -c 5          # 每条 5 条评论
zhihu feeds -c 0          # 仅推荐内容，不带评论

# 话题
zhihu topic <topic_id> --questions
```

### 互动

```bash
# 赞同 / 取消赞同
zhihu vote <answer_id>
zhihu vote <answer_id> --undo

# 关注 / 取消关注问题
zhihu follow-question <question_id>
zhihu follow-question <question_id> --undo
```

### 创作

发布提问、想法、文章时，**描述/正文均支持 HTML 富文本**（如 `<p>`、`<strong>`、`<a>` 等）。

```bash
# 发布提问
zhihu ask "如何学习 Python？"
zhihu ask "什么是机器学习？" -d "请详细解释" -t 19550517 -t 19551275

# 发布想法（标题 + 可选正文，正文可用 HTML）
zhihu pin "今天天气真好！"
zhihu pin "标题" -c "想法正文内容"

# 发布文章
zhihu article "文章标题" "文章内容"
zhihu article "标题" "内容" -t 19550517

# 带图片发布（-i 可重复使用以添加多张图片）
zhihu ask "求推荐" -d "详情" -i photo.jpg
zhihu pin "标题" -c "正文" -i image1.jpg -i image2.jpg
zhihu article "标题" "内容" -i cover.jpg

# 删除自己发布的内容（会提示确认，加 -y 跳过确认）
zhihu delete-question <问题ID>
zhihu delete-pin <想法ID>
zhihu delete-article <文章ID>
zhihu delete-question 12345678 -y
```

### 其他

```bash
zhihu collections
zhihu notifications
zhihu --version
zhihu -v search "Python"   # 调试日志
zhihu --help
```

## 后续开发

- [ ] 发布回答
- [ ] 发布评论
- [ ] 发布视频


## 架构

```
CLI (click) → ZhihuClient (requests)
                  ↓ API 请求
              Zhihu V4 API → JSON 响应

zhihu_cli/
├── config.py      # 集中配置：路径、URL、统一 UA/Chrome 版本
├── auth.py        # Cookie 管理、QR 码登录、scan_info 轮询
├── client.py      # ZhihuClient — 所有 API 调用封装
├── display.py     # Rich 终端输出
└── commands/      # Click 子命令
```

使用 `requests` 库通过知乎 V4 API 获取数据。登录认证通过二维码扫描或手动提供 Cookie 完成。

## 工作原理

1. **认证** — 通过 `zhihu login --qrcode`（二维码扫码）或 `zhihu login --cookie "z_c0=...; _xsrf=...; d_c0=..."`（手动粘贴 Cookie）完成登录，登录态保存于 `~/.zhihu-cli/cookies.json`。
2. **登录态校验** — 登录后通过 `/api/v4/me` 接口验证会话有效性。
3. **数据获取** — 使用 requests 通过知乎 V4 API 获取结构化 JSON 数据。
4. **CLI 展示** — 使用 Rich 库渲染美观的终端表格输出。

## 注意事项

- Cookie 存储在 `~/.zhihu-cli/cookies.json`，权限 `0600`
- 需要检查或浏览时可使用全局 `--readonly` / `--read-only`，避免误触发布、互动或删除
- `zhihu status` 只检查本地已保存的 cookie，不发起网络请求
- `zhihu login --cookie` 要求 Cookie 至少包含 `z_c0`、`_xsrf`、`d_c0`
- 用户查询使用 URL Token（即知乎个人主页的路径部分，如 `zhihu.com/people/xxx` 中的 `xxx`）
- 二维码登录使用知乎官方 API，无需安装 Playwright
- 浏览器指纹版本号集中管理于 `config.py` 的 `CHROME_VERSION`，修改一处即可全局生效

## 网络安全设计

本工具在设计与实现上遵循以下安全原则，以降低凭证与隐私风险：

- **凭证仅存本地**  
  登录态（Cookie）仅写入用户本机 `~/.zhihu-cli/cookies.json`，文件权限为 `0600`（仅当前用户可读写）。程序不会将 Cookie 或任何登录凭证上传至本工具维护方或第三方服务。

- **全程 HTTPS**  
  所有与知乎的通信均使用 HTTPS，请求仅发往知乎官方域名（如 `www.zhihu.com`、`api.zhihu.com`），避免凭证或内容在网络上明文传输。

- **无密码落地**  
  支持两种登录方式：二维码扫码（调用知乎官方登录 API，由用户在手机端完成授权）和手动粘贴 Cookie。本工具不收集、不存储账号密码。

- **最小权限与最小请求**  
  仅请求完成当前命令所需的知乎 API，不额外拉取或上报用户数据；Cookie 仅用于向知乎证明身份，不用于其他用途。

- **可审计与可复现**  
  项目开源，依赖列表在 `pyproject.toml` 中声明，无混淆或闭源运行时；用户可自行审查代码与依赖，或在隔离环境中安装运行。

建议仅在可信环境中使用本工具，并妥善保管本地 Cookie 文件；通过 `zhihu logout` 可清除本地保存的登录态。

## 发布到 PyPI

发布前请确认 `pyproject.toml` 中 `version` 已更新（每次发布需递增）。

```bash
# 1. 安装构建与上传工具
pip install build twine

# 2. 在项目根目录构建（生成 dist/ 下的 wheel 与 sdist）
python -m build

# 3. 检查打包内容（可选）
twine check dist/*

# 4. 上传到 PyPI（需已配置 PyPI 账号或 token）
twine upload dist/*
```

- 首次上传需在 [PyPI](https://pypi.org) 注册并配置 API Token；使用 token 时用户名填 `__token__`，密码填 token 值。
- 若使用 TestPyPI 测试：`twine upload --repository testpypi dist/*`

## License

Apache License 2.0
