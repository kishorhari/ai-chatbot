# Security Policy

## Supported versions

This project is pre-1.0 and under active milestone development. Security fixes are
applied to the latest tagged milestone and `main`. Older milestone tags are not
maintained.

| Version | Supported |
|---------|:---------:|
| `main` / latest `vX.Y.Z-mN` tag | ✅ |
| Older milestone tags | ❌ |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report privately using GitHub's
[private vulnerability reporting](https://github.com/kishorhari/ai-chatbot/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab). If that is
unavailable, contact the maintainer directly.

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal proof of concept if possible).
- Affected version/commit and configuration.
- Any suggested remediation.

You can expect an acknowledgement within a few days. Once the issue is confirmed and
fixed, we will coordinate disclosure and credit you in the advisory unless you prefer
to remain anonymous.

## Scope and hardening notes

This repository's design already addresses several common classes of issue, which
contributors must preserve:

- **Secrets** are typed as `SecretStr`, read only through the `Settings` object, and
  redacted from logs and reprs (verified by test). Never log a secret, and never
  read configuration via scattered `os.environ` access.
- **`.env`** is git-ignored; only `.env.example` (no real values) is committed.
- **No vendor/transport exception escapes an adapter** — failures are mapped to the
  domain `LLMError` taxonomy, avoiding accidental leakage of internal detail.

When future milestones add authentication, multi-tenancy, webhooks, and cloud
provider credentials (see [ROADMAP.md](ROADMAP.md)), security review of those
boundaries — tenant isolation, webhook signature verification, and credential
handling in particular — is expected as part of the relevant PR.
