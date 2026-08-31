<h1 align="center">oh-my-zhihu-cli</h1>

<p align="center">
  <a href="README.md">🇨🇳 中文</a>
  <span>&nbsp;·&nbsp;</span>
  <strong>🇬🇧 English</strong>
</p>

<p align="center">
  <a href="https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli/actions/workflows/ci.yml"><img src="https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="AGPL-3.0 license"></a>
  <img src="https://img.shields.io/badge/version-0.3.0-1772F6.svg" alt="Version 0.3.0">
</p>

A command-line client for personal Zhihu workflows. This project is based on
[BAIGUANGMEI/zhihu-cli](https://github.com/BAIGUANGMEI/zhihu-cli) and adds draft
reading, read-only protection, account profiles, multi-format backups, network
retry controls, and guarded write flows.

> Unofficial community derivative. Zhihu endpoints may change. Use `--dry-run`
> or `--readonly` before publishing, interacting, or deleting content.

Current version: `0.3.0`

## Features

- Search questions, answers, articles, users, and topics
- Read questions, answers, published articles, ideas, and collections
- List article, idea, answer, and video drafts
- Read full article drafts and export drafts as JSON or Markdown
- Search drafts by title or text
- Isolate multiple accounts with named profiles
- Configure GET timeout and bounded retries
- Block publishing, interaction, and deletion with global `--readonly`
- Preview answers and comments; require explicit `--execute` to send them
- Render terminal tables with Rich and support structured JSON output

## Installation

### Install from GitHub

```bash
uv tool install git+https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli.git@v0.3.0
```

### Editable installation for development

```bash
git clone https://github.com/JunkaiWang-TheoPhy/oh-my-zhihu-cli.git
cd oh-my-zhihu-cli
uv tool install --editable .
```

Verify the installation:

```bash
zhihu --version
zhihu --help
```

## Login and profiles

```bash
zhihu login --qrcode
zhihu status
zhihu whoami
zhihu profiles
```

The default session is stored at `~/.zhihu-cli/cookies.json` with file mode
`0600`. Named profiles use isolated files:

```text
~/.zhihu-cli/profiles/<name>/cookies.json
```

For example:

```bash
zhihu --profile personal login --qrcode
zhihu --profile work login --qrcode
zhihu --profile personal drafts
zhihu --profile work whoami
```

Never commit or log cookies, tokens, QR-code images, or personal draft
backups.

## Read-only reading

Use the global `--readonly` flag for query workflows:

```bash
zhihu --readonly search "quantum gravity"
zhihu --readonly question <question_id>
zhihu --readonly answer <answer_id>
zhihu --readonly article-read <article_id>
zhihu --readonly pin-read <pin_id>
zhihu --readonly collection <collection_id>
```

`--read-only` is an alias for `--readonly`.

## Drafts

List article drafts by default:

```bash
zhihu --readonly drafts
zhihu --readonly drafts --all
zhihu --readonly drafts --id <article_draft_id>
```

Select another draft type:

```bash
zhihu --readonly drafts --type idea
zhihu --readonly drafts --type answer
zhihu --readonly drafts --type video
```

Search and export:

```bash
zhihu --readonly drafts --search "gravity" --all
zhihu --readonly drafts --all --json > drafts.json
zhihu --readonly drafts --all --export-markdown ~/zhihu-drafts.md
```

## Backup and diff

```bash
zhihu --readonly drafts-backup ~/ZhihuBackup --type article --all
zhihu --readonly drafts-backup ~/ZhihuBackup --type answer --all
zhihu drafts-diff ~/ZhihuBackup/before.json ~/ZhihuBackup/after.json
```

`drafts-backup` writes raw JSON and a readable Markdown snapshot.
`drafts-diff` only reads local files and does not contact Zhihu.

## Network options

```bash
zhihu --timeout 30 --retry 2 search "AI"
```

- `--timeout` defaults to 15 seconds
- `--retry` defaults to 0 and accepts up to 5 retries
- Retries apply only to GET requests
- Publish, interaction, and delete requests are never automatically retried
- Proxy settings use `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY`

## Write safety

Existing publishing and deletion commands support previews:

```bash
zhihu pin "A title" --dry-run
zhihu article "A title" "Body" --dry-run
zhihu delete-pin <pin_id> --dry-run
```

Answer and comment commands are preview-only by default:

```bash
zhihu answer-post <question_id> --file answer.md
zhihu comment answer <answer_id> "A comment"
```

Pass `--execute` explicitly to send the request:

```bash
zhihu answer-post <question_id> --file answer.md --execute
zhihu comment answer <answer_id> "A comment" --execute
```

Global read-only mode blocks these operations before a client is created or a
request is sent:

```bash
zhihu --readonly ask "A question"
zhihu --readonly pin "An idea"
zhihu --readonly article "A title" "Body"
zhihu --readonly answer-post <question_id> --execute --content "Body"
zhihu --readonly comment answer <answer_id> "A comment"
zhihu --readonly vote <answer_id>
zhihu --readonly follow-question <question_id>
zhihu --readonly delete-pin <pin_id>
```

## Other commands

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

Most data commands support `--json`:

```bash
zhihu --readonly hot --json
zhihu --readonly whoami --json
```

## Development

```bash
uv sync --dev
uv run pytest -q
uv run ruff check zhihu_cli/commands/backup.py tests/test_extensions.py
uv build --no-sources
```

Tests requiring a real login session should be marked as `integration`. The
default test suite does not publish, comment, like, follow, or delete anything.

## License and upstream attribution

This project is licensed under the GNU Affero General Public License v3 only;
see [LICENSE](LICENSE).

This is a derivative of
[BAIGUANGMEI/zhihu-cli](https://github.com/BAIGUANGMEI/zhihu-cli). The upstream
Apache License 2.0 text is preserved in
[LICENSE-APACHE-2.0](LICENSE-APACHE-2.0), with attribution details in
[NOTICE](NOTICE).

See [SECURITY.md](SECURITY.md) for credential-handling guidance.
