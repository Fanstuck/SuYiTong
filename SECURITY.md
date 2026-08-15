# Security Policy

## Secrets and local research data

SuYiTong reads third-party API credentials from the local file:

```text
runtime/.jiuwenswarm/config/.env
```

The entire `runtime/` directory is excluded from Git. Never place real credentials in source files, screenshots, issues, pull requests, or committed examples. Copy `config/jiuwenswarm.env.example` locally and replace placeholders only inside the ignored runtime directory.

The public repository must not contain:

- API keys, bearer tokens, custom authorization headers, private keys or certificates;
- SQLite databases, embedding caches, JSONL experiment logs or user research inputs;
- generated runtime workspaces, model checkpoints or local application logs.

Environment read APIs return only whether a key is configured and never return the original value.

## Reporting a vulnerability

Do not disclose a credential or private research document in a public issue. Contact the repository owner privately with a minimal reproduction and redact sensitive values.
