"""Aegis admin CLI.

Usage:
    python -m app.cli verify-audit
    python -m app.cli hash-password
"""
from __future__ import annotations

import argparse
import getpass
import sys

from .audit_signer import verify_chain


def cmd_verify_audit(_args) -> int:
    result = verify_chain()
    if result["ok"]:
        print(f"✓ Ledger intact ({result['total']} entries)")
        return 0
    print("✗ Tampering detected!")
    print(f"  first break at seq #{result['first_break_seq']}")
    print(f"  reason: {result['first_break_reason']}")
    print(f"  total entries scanned: {result['total']}")
    return 2


def cmd_hash_password(_args) -> int:
    import bcrypt
    pw = getpass.getpass("New admin password: ").encode("utf-8")
    if not pw:
        print("empty password — aborted", file=sys.stderr)
        return 1
    print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegis", description="Aegis admin CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify-audit", help="Walk the signed ledger and report integrity")
    sub.add_parser("hash-password", help="Generate a bcrypt hash to paste into AEGIS_ADMIN_PASSWORD_HASH")
    args = parser.parse_args(argv)
    handlers = {"verify-audit": cmd_verify_audit, "hash-password": cmd_hash_password}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
