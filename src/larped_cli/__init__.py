"""larped: check whether a Solana token's tech claims hold up, from the terminal.

A thin client for the public Larped API. No keys, no dependencies beyond Python itself.

  larped <mint>            readable verdict, red flags, proofs and money trail
  larped <mint> --json     the full report as JSON (for bots and scripts)
  larped <mint> --fresh    rescan now instead of using a saved scan

Set LARPED_API to use another instance (default https://larped-three.vercel.app).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

__version__ = "0.1.0"
API = os.environ.get("LARPED_API", "https://larped-three.vercel.app").rstrip("/")
UA = f"larped-cli/{__version__}"


def fetch(path: str, timeout: int = 300) -> tuple[int, dict]:
    req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except (ValueError, json.JSONDecodeError):
            return e.code, {}


def get_report(mint: str, fresh: bool = False) -> dict:
    """Saved report first (free, not rate-limited); scan only when there is none, it is stale, or --fresh."""
    if not fresh:
        status, body = fetch(f"/api/report/{mint}", timeout=30)
        if status == 200 and not body.get("stale"):
            return body
    status, body = fetch(f"/api/scan/{mint}?fresh=true" if fresh else f"/api/scan/{mint}")
    if status == 200:
        return body
    reason = body.get("detail") or {429: "too many scans from your connection, try again later",
                                     503: "the scan budget is used up for now"}.get(status, f"HTTP {status}")
    raise SystemExit(f"larped: {reason}")


# --- formatting --------------------------------------------------------------------------------------------

def _colour(enabled: bool):
    def c(text, code):
        return f"\033[{code}m{text}\033[0m" if enabled else text
    return c


def short(a: str) -> str:
    return f"{a[:4]}…{a[-4:]}" if a and len(a) > 12 else (a or "?")


def when(ts) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ts else ""


def money_tree(m: dict) -> list[str]:
    """The money trail as indented text: who funded whom, with share of supply."""
    if not m or not m.get("nodes"):
        return []
    by = {n["id"]: n for n in m["nodes"]}
    kids: dict[str, list[str]] = {}
    for e in m.get("edges", []):
        if e["from"] in by and e["to"] in by and e["from"] != e["to"]:
            kids.setdefault(e["from"], []).append(e["to"])
    has_parent = {k for v in kids.values() for k in v}
    out, seen = [], set()

    def label(n):
        roles = [r for r in n.get("roles", []) if r not in ("holder", "funder") or len(n["roles"]) == 1]
        pct = f"{n['pct']:.2f}%" if n.get("pct") else ""
        return f"{short(n['id'])}  {' · '.join(roles)}  {pct}".rstrip()

    def walk(nid, prefix, last):
        if nid in seen:
            return
        seen.add(nid)
        out.append(f"{prefix}{'└─ ' if last else '├─ '}{label(by[nid])}")
        ch = kids.get(nid, [])
        for i, c in enumerate(ch):
            walk(c, prefix + ("   " if last else "│  "), i == len(ch) - 1)

    for g in sorted(m.get("clusters", []), key=lambda c: (not c.get("has_creator"), -c["pct"])):
        members = [n for n in m["nodes"] if n.get("cluster") == g["id"]]
        roots = [n["id"] for n in members if n["id"] not in has_parent] or [members[0]["id"]]
        title = "The creator's side" if g.get("has_creator") else f"Linked group {g['id'] + 1}"
        out.append(f"  {title}: {g['wallets']} wallets share a funding source, {g['pct']:.1f}% of supply")
        for i, r in enumerate(roots):
            walk(r, "    ", i == len(roots) - 1)
    indep = sorted((n for n in m["nodes"] if n["id"] not in seen and n.get("pct") and "program" not in n.get("roles", [])),
                   key=lambda n: -n["pct"])
    if indep:
        out.append(f"  Independent holders: {len(indep)} (largest {indep[0]['pct']:.2f}%)")
    pools = sum(n.get("pct") or 0 for n in m["nodes"] if "program" in n.get("roles", []))
    if pools:
        out.append(f"  Pools and programs hold {pools:.1f}% of supply")
    return out


def render(r: dict, colour: bool = False) -> str:
    c = _colour(colour)
    flags, proofs, context = r.get("flags", []), r.get("proofs", []), r.get("context", [])
    tone = 31 if flags and not proofs else 34 if proofs and not flags else 1
    t = r.get("token") or {}
    lines = [f"{c(t.get('name') or 'Unnamed token', 1)} ({t.get('symbol') or '?'})  {r.get('mint', '')}",
             c(r.get("headline") or r.get("result", ""), f"1;{tone}"),
             f"{c(f'{len(flags)} red flag' + ('' if len(flags) == 1 else 's'), 31)} · "
             f"{c(f'{len(proofs)} proof' + ('' if len(proofs) == 1 else 's'), 34)}", ""]
    if flags:
        lines += [c("Red flags", "1;31")] + [f"  • {f['text']}" for f in flags]
    if proofs:
        lines += [c("Proofs", "1;34")] + [f"  • {p['text']}" for p in proofs]
    if not proofs:
        lines.append("  No verified program or linked public code. Unproven is not the same as fake.")
    if context:
        lines += [c("Context", 2)] + [f"  • {x['text']}" for x in context]
    tree = money_tree(next((ch.get("facts") for ch in r.get("checks", []) if ch["check"] == "map"), None))
    if tree:
        lines += ["", c("Money trail", 1)] + tree
    events = r.get("timeline") or []
    if events:
        lines += ["", c("Timeline", 1)] + [f"  {when(e['time'])}  {e['text']}" for e in events]
    seen = r.get("views")
    lines += ["", c(f"Checked {seen} times on Larped. " if seen and seen > 1 else "", 2)
              + c(f"Full report: {API}/?mint={r.get('mint', '')}", 2),
              c("Signals come from public data and describe what happened, not intent. Not financial advice.", 2)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if args[0] in ("-V", "--version"):
        print(__version__)
        return 0
    mint = next((a for a in args if not a.startswith("-")), "")
    if not 32 <= len(mint) <= 44:
        print("larped: give a Solana token mint address", file=sys.stderr)
        return 2
    report = get_report(mint, fresh="--fresh" in args)
    if "--json" in args:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report, colour=sys.stdout.isatty() and not os.environ.get("NO_COLOR")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
