# Security policy

## Credential handling

This project uses local Zhihu cookies for authentication. Cookies are stored
outside the repository under `~/.zhihu-cli/` and should remain protected with
file mode `0600`. Never commit cookies, access tokens, QR-code images, private
draft exports, or `.env` files.

The public repository does not collect credentials or send them to the project
maintainers. Before opening an issue, remove personal content, request headers,
cookies, and tokens from logs and screenshots.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository when
available. If that feature is unavailable, open a minimal issue containing no
credentials or personal data and ask for a private contact channel.
