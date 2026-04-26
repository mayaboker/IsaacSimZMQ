#!/usr/bin/env python3
"""
Fail-fast checker for non-portable USD references.

Usage:
  python3 tools/check_usd_external_refs.py assets/is40-zmq.usd
  python3 tools/check_usd_external_refs.py assets/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _collect_usd_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            print(f"[usd-check] ERROR: Path not found: {p}")
            continue
        if p.is_file() and p.suffix.lower() in {".usd", ".usda", ".usdc"}:
            files.append(p)
            continue
        if p.is_dir():
            files.extend(
                sorted(
                    f for f in p.rglob("*")
                    if f.is_file() and f.suffix.lower() in {".usd", ".usda", ".usdc"}
                )
            )
    return files


def _classify_asset_path(asset_path: str) -> str | None:
    ap = asset_path.strip()
    if not ap:
        return None
    if ap.startswith(("http://", "https://", "omniverse://")):
        return "remote"
    if ap.startswith("/"):
        return "absolute-local"
    return None


def _scan_with_pxr(usd_path: Path) -> list[tuple[str, str, str]]:
    # Defer import so the script can print a clear message if pxr is unavailable.
    from pxr import Usd  # type: ignore

    findings: list[tuple[str, str, str]] = []
    stage = Usd.Stage.Open(str(usd_path))
    if not stage:
        findings.append(("error", "/", "Unable to open stage"))
        return findings

    for prim in stage.TraverseAll():
        prim_path = str(prim.GetPath())

        refs = prim.GetMetadata("references")
        if refs:
            items = []
            for attr in ("prependedItems", "explicitItems", "appendedItems", "addedItems"):
                if hasattr(refs, attr):
                    items.extend(getattr(refs, attr) or [])
            for item in items:
                ap = getattr(item, "assetPath", "")
                kind = _classify_asset_path(ap)
                if kind:
                    findings.append((kind, prim_path, ap))

        payloads = prim.GetMetadata("payload") or prim.GetMetadata("payloads")
        if payloads:
            items = []
            for attr in ("prependedItems", "explicitItems", "appendedItems", "addedItems"):
                if hasattr(payloads, attr):
                    items.extend(getattr(payloads, attr) or [])
            for item in items:
                ap = getattr(item, "assetPath", "")
                kind = _classify_asset_path(ap)
                if kind:
                    findings.append((kind, prim_path, ap))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check USD files for external/non-portable references.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="USD file(s) or directory(ies) to scan recursively",
    )
    parser.add_argument(
        "--allow-absolute-local",
        action="store_true",
        help="Do not fail on absolute local paths (still reports them)",
    )
    args = parser.parse_args()

    usd_files = _collect_usd_files(args.paths)
    if not usd_files:
        print("[usd-check] ERROR: No USD files found in input paths.")
        return 2

    try:
        # Probe pxr once so we can fail with a helpful message.
        from pxr import Usd  # type: ignore  # noqa: F401
    except Exception as exc:
        print("[usd-check] ERROR: Could not import pxr/USD Python bindings.")
        print(f"[usd-check] Details: {exc}")
        print("[usd-check] Run this with Isaac Sim Python or set USD pxr environment.")
        return 3

    total_findings = 0
    blocked_findings = 0

    for usd_path in usd_files:
        findings = _scan_with_pxr(usd_path)
        if not findings:
            print(f"[usd-check] OK: {usd_path}")
            continue

        print(f"[usd-check] Findings in: {usd_path}")
        for kind, prim_path, asset_path in findings:
            total_findings += 1
            blocks = kind == "remote" or (kind == "absolute-local" and not args.allow_absolute_local)
            if blocks:
                blocked_findings += 1
            block_tag = "BLOCK" if blocks else "WARN "
            print(f"  [{block_tag}] {kind:14} prim={prim_path} asset={asset_path}")

    if blocked_findings > 0:
        print(f"[usd-check] FAIL: {blocked_findings} blocking reference(s) found.")
        return 1

    if total_findings > 0:
        print(f"[usd-check] PASS with warnings: {total_findings} non-blocking reference(s).")
        return 0

    print("[usd-check] PASS: no external/non-portable references found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
