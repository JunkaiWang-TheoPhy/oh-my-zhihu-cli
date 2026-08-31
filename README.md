<h1 align="center">oh-my-zhihu-cli</h1>

<p align="center">
  <strong>🇨🇳 中文</strong>
  <span>&nbsp;·&nbsp;</span>
  <a href="README_EN.md">🇬🇧 English</a>
</p>

<p align="center">
  <a href="https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli/actions/workflows/ci.yml"><img src="https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="AGPL-3.0 license"></a>
  <img src="https://img.shields.io/badge/version-0.3.0-1772F6.svg" alt="Version 0.3.0">
</p>

一个面向个人账号的知乎命令行工具。项目基于上游
[BAIGUANGMEI/zhihu-cli](https://github.com/BAIGUANGMEI/zhihu-cli)，并扩展了草稿读取、只读保护、profile、多格式备份和安全写入流程。

> 非官方社区衍生项目。知乎接口可能变化；涉及发布、互动和删除的命令请先使用 `--dry-run` 或 `--readonly` 检查。

当前版本：`0.3.0`

## 功能

- 搜索问题、回答、文章、用户和话题
- 查看问题、回答、已发布文章、想法和收藏夹
- 查看文章、想法、回答和视频草稿
- 草稿全文读取、关键词搜索、JSON/Markdown 导出
- 多账号 profile 隔离
- GET 请求超时和有限重试
- 全局 `--readonly` 保护，阻止发布、互动和删除
- 发布回答、评论前默认 dry-run，明确使用 `--execute` 才发送
- Rich 终端表格和 JSON 输出

## 安装

### 从 GitHub 安装

```bash
uv tool install git+https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli.git@v0.3.0
```

### 本地开发安装

```bash
git clone https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli.git
cd oh-my-zhihu-cli
uv tool install --editable .
```

检查安装：

```bash
zhihu --version
zhihu --help
```

## 登录和账号

```bash
zhihu login --qrcode
zhihu status
zhihu whoami
zhihu profiles
```

默认登录态保存在 `~/.zhihu-cli/cookies.json`，权限为 `0600`。命名 profile 保存在：

```text
~/.zhihu-cli/profiles/<name>/cookies.json
```

例如：

```bash
zhihu --profile personal login --qrcode
zhihu --profile work login --qrcode
zhihu --profile personal drafts
zhihu --profile work whoami
```

仓库和日志中不得保存 Cookie、Token、二维码或个人草稿备份。

## 只读阅读

推荐把查询命令放在全局 `--readonly` 模式下：

```bash
zhihu --readonly search "量子引力"
zhihu --readonly question <question_id>
zhihu --readonly answer <answer_id>
zhihu --readonly article-read <article_id>
zhihu --readonly pin-read <pin_id>
zhihu --readonly collection <collection_id>
```

`--read-only` 是同义写法。

## 草稿

默认查看文章草稿：

```bash
zhihu --readonly drafts
zhihu --readonly drafts --all
zhihu --readonly drafts --id <article_draft_id>
```

其他草稿类型：

```bash
zhihu --readonly drafts --type idea
zhihu --readonly drafts --type answer
zhihu --readonly drafts --type video
```

搜索和导出：

```bash
zhihu --readonly drafts --search "引力" --all
zhihu --readonly drafts --all --json > drafts.json
zhihu --readonly drafts --all --export-markdown ~/zhihu-drafts.md
```

## 备份和 diff

```bash
zhihu --readonly drafts-backup ~/ZhihuBackup --type article --all
zhihu --readonly drafts-backup ~/ZhihuBackup --type answer --all
zhihu drafts-diff ~/ZhihuBackup/before.json ~/ZhihuBackup/after.json
```

`drafts-backup` 会生成 JSON 原始数据和 Markdown 阅读版本；`drafts-diff` 只读取本地文件，不访问知乎。

## 网络选项

```bash
zhihu --timeout 30 --retry 2 search "AI"
```

- `--timeout` 默认 15 秒
- `--retry` 默认 0，最多允许 5 次重试
- 只对 GET 请求重试
- 不会自动重试发布、互动或删除请求
- 代理使用 `HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY` 环境变量

## 写入安全

已有发布和删除命令支持预览：

```bash
zhihu pin "标题" --dry-run
zhihu article "标题" "正文" --dry-run
zhihu delete-pin <pin_id> --dry-run
```

回答和评论默认只显示预览：

```bash
zhihu answer-post <question_id> --file answer.md
zhihu comment answer <answer_id> "评论内容"
```

明确加 `--execute` 才会发送请求：

```bash
zhihu answer-post <question_id> --file answer.md --execute
zhihu comment answer <answer_id> "评论内容" --execute
```

全局只读模式会在创建客户端和发请求前拦截以下操作：

```bash
zhihu --readonly ask "问题"
zhihu --readonly pin "想法"
zhihu --readonly article "标题" "正文"
zhihu --readonly answer-post <question_id> --execute --content "正文"
zhihu --readonly comment answer <answer_id> "评论"
zhihu --readonly vote <answer_id>
zhihu --readonly follow-question <question_id>
zhihu --readonly delete-pin <pin_id>
```

## 其他命令

```bash
zhihu hot
zhihu feed
zhihu feeds
zhihu topic <topic_id>
zhihu user <url_token>
zhihu user-answers <url_token>
zhihu user-articles <url_token>
zhihu followers <url_token>
zhihu following <url_token>
zhihu collections
zhihu notifications
```

数据查询命令通常支持 `--json`：

```bash
zhihu --readonly hot --json
zhihu --readonly whoami --json
```

## 开发

```bash
uv sync --dev
uv run pytest -q
uv run ruff check zhihu_cli/commands/backup.py tests/test_extensions.py
uv build --no-sources
```

需要真实登录态的测试应单独标记为 `integration`，默认测试不会发布、评论、点赞、关注或删除。

## 许可证和上游归属

本项目使用 GNU Affero General Public License v3 only，详见 [LICENSE](LICENSE)。

本项目是 [BAIGUANGMEI/zhihu-cli](https://github.com/BAIGUANGMEI/zhihu-cli) 的衍生项目。上游 Apache License 2.0 文本保存在 [LICENSE-APACHE-2.0](LICENSE-APACHE-2.0)，归属说明见 [NOTICE](NOTICE)。

项目安全说明见 [SECURITY.md](SECURITY.md)。
