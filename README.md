# oh-my-zhihu-cli

一个面向个人账号的知乎命令行工具，基于上游
[BAIGUANGMEI/zhihu-cli](https://github.com/BAIGUANGMEI/zhihu-cli) 维护，加入了草稿读取、账号 profile、备份、diff、网络重试和写入保护。

这是一个非官方的社区衍生项目。知乎接口可能变化，涉及发布、互动和删除的功能请谨慎使用。

版本：`0.3.0`

## 安装

```bash
git clone https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli.git
cd oh-my-zhihu-cli
uv tool install --editable .
```

从本仓库安装不会被 PyPI 上游升级覆盖。

## 登录

```bash
zhihu login --qrcode
zhihu status
zhihu whoami
```

默认登录态保存在 `~/.zhihu-cli/cookies.json`，权限为 `0600`。

## 账号 profile

```bash
zhihu profiles
zhihu --profile work login --qrcode
zhihu --profile work drafts
zhihu --profile personal whoami
```

命名 profile 保存在 `~/.zhihu-cli/profiles/<name>/cookies.json`。仓库中不会保存任何 Cookie、Token 或草稿备份。

## 只读内容

```bash
zhihu --readonly article-read <article_id>
zhihu --readonly pin-read <pin_id>
zhihu --readonly collection <collection_id>
zhihu --readonly search "量子引力"
```

## 草稿

```bash
zhihu --readonly drafts
zhihu --readonly drafts --type idea
zhihu --readonly drafts --type answer
zhihu --readonly drafts --type video
zhihu --readonly drafts --search "引力"
zhihu --readonly drafts --all --export-markdown ~/zhihu-drafts.md
```

当前支持文章、想法、回答和视频草稿列表；文章草稿可以用 `--id` 查看全文。

## 备份和 diff

```bash
zhihu --readonly drafts-backup ~/ZhihuBackup --type article --all
zhihu drafts-diff ~/ZhihuBackup/before.json ~/ZhihuBackup/after.json
```

备份目录包含 JSON 原始数据和 Markdown 阅读版本。

## 网络选项

```bash
zhihu --timeout 30 --retry 2 search "AI"
```

`--retry` 只对 GET 请求生效，不会自动重试发布、互动或删除请求。HTTP 代理继续使用 `HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY` 环境变量。

## 写入安全

已有写入命令支持预览：

```bash
zhihu pin "标题" --dry-run
zhihu article "标题" "正文" --dry-run
zhihu delete-pin <id> --dry-run
```

回答和评论默认只预览，必须显式 `--execute` 才会发送：

```bash
zhihu answer-post <question_id> --file answer.md
zhihu answer-post <question_id> --file answer.md --execute
zhihu comment answer <answer_id> "评论内容"
zhihu comment answer <answer_id> "评论内容" --execute
```

全局只读模式会在请求前拦截发布、回答、评论、点赞、关注和删除：

```bash
zhihu --readonly pin "不会发布"
zhihu --readonly answer-post <question_id> --execute --content "不会发送"
```

## 开发验证

```bash
python -m compileall zhihu_cli
pytest
```

需要真实登录态的测试应单独标记为 `integration`，不在默认测试中发送写请求。

## 许可证和上游归属

本项目使用 GNU Affero General Public License v3 only，详见 [LICENSE](LICENSE)。

上游 Apache License 2.0 文本保存在 [LICENSE-APACHE-2.0](LICENSE-APACHE-2.0)，上游归属说明见 [NOTICE](NOTICE)。
