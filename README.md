# larped-cli

Check whether a Solana token's tech claims hold up, from your terminal.

`larped` is a small client for the public [Larped](https://larped-three.vercel.app) API. It needs no API keys and has no dependencies beyond Python 3.10+.

## Install

```bash
uv tool install git+https://github.com/FransmanKC/larped-cli
# or
pipx install git+https://github.com/FransmanKC/larped-cli
```

## Use

```bash
larped <mint>            # verdict, red flags, proofs, money trail, timeline
larped <mint> --json     # the full report as JSON, for bots and scripts
larped <mint> --fresh    # rescan now instead of using a saved scan
```

A saved scan is used when one exists (fast, no limit). New scans are rate-limited per connection.

## What the verdict means

- **Red flags** are facts that match the larp pattern, for example the creator selling within hours, linked wallets buying in the launch block, or a linked project that never mentions this token.
- **Proofs** are independent evidence for the tech claims: a verified, independently used on-chain program, or a public repository that names this token's address.
- **Unproven is not the same as fake.** Signals come from public data and describe what happened, not intent. Not financial advice.

## License

MIT
