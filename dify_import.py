"""
dify_import.py -- Auto-upload ArchAI Builder Markdown to Dify Knowledge Base

Usage:
  python dify_import.py                          # upload all .md under output/markdown/
  python dify_import.py --architect "Tadao Ando"  # single architect
  python dify_import.py --dry-run                # scan only, no upload

Prerequisites:
  1. Create a Knowledge Base in Dify web UI
  2. Get Dataset ID (from URL in knowledge base settings)
  3. Get API Key (Knowledge Base settings -> API Management)
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

DIFY_API_BASE = os.environ.get("DIFY_API_BASE", "https://api.dify.ai/v1")
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")
DIFY_DATASET_ID = os.environ.get("DIFY_DATASET_ID", "")

REQUEST_TIMEOUT = 60
RATE_LIMIT_DELAY = 1.5

MARKDOWN_DIR = Path(__file__).resolve().parent / "output" / "markdown"


def list_markdown_files(base_dir: Path, architect_filter: str = "") -> list[Path]:
    """Scan output/markdown/ for .md files."""
    if not base_dir.exists():
        print(f"[ERROR] Directory not found: {base_dir}")
        return []

    if architect_filter:
        safe = re.sub(r"[^\w\-_]", "_", architect_filter)
        search_dir = base_dir / safe
        if not search_dir.exists():
            print(f"[ERROR] Architect dir not found: {search_dir}")
            return []
        files = sorted(search_dir.glob("*.md"))
    else:
        files = sorted(base_dir.rglob("*.md"))

    return [f for f in files if f.stat().st_size > 100]


def upload_document(name: str, text: str, dataset_id: str, api_key: str) -> dict | None:
    """
    Upload text document to Dify KB.
    POST /v1/datasets/{dataset_id}/document/create_by_text
    """
    url = f"{DIFY_API_BASE}/datasets/{dataset_id}/document/create_by_text"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": name,
        "text": text,
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 or resp.status_code == 201:
            return resp.json()
        else:
            print(f"    HTTP {resp.status_code}: {resp.text[:300]}")
            return None
    except requests.exceptions.Timeout:
        print(f"    [TIMEOUT] Request timeout")
        return None
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def check_document_status(document_id: str, dataset_id: str, api_key: str) -> str:
    """Check document indexing status."""
    url = f"{DIFY_API_BASE}/datasets/{dataset_id}/documents/{document_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("indexing_status", "unknown")
        return "unknown"
    except Exception:
        return "unknown"


def import_all(
    dataset_id: str = "",
    api_key: str = "",
    architect_filter: str = "",
    dry_run: bool = False,
) -> dict:
    """Main: scan and upload all Markdown files."""
    ds_id = dataset_id or DIFY_DATASET_ID
    key = api_key or DIFY_API_KEY

    if not ds_id or not key:
        print("[ERROR] Please set DIFY_DATASET_ID and DIFY_API_KEY")
        print("   Option 1: export DIFY_DATASET_ID=xxx DIFY_API_KEY=xxx")
        print("   Option 2: python dify_import.py --dataset-id xxx --api-key xxx")
        return {"total": 0, "uploaded": 0, "failed": 0, "skipped": 0, "results": []}

    files = list_markdown_files(MARKDOWN_DIR, architect_filter)
    if not files:
        print("[INFO] No Markdown files found")
        return {"total": 0, "uploaded": 0, "failed": 0, "skipped": 0, "results": []}

    print(f"[SCAN] Found {len(files)} files")
    if architect_filter:
        print(f"   Filter: {architect_filter}")
    if dry_run:
        print(f"   Mode: DRY RUN (no actual upload)")
    print()

    stats = {"total": len(files), "uploaded": 0, "failed": 0, "skipped": 0, "results": []}

    for i, filepath in enumerate(files, 1):
        parts = filepath.parts
        architect_name = parts[-2] if len(parts) >= 2 else "unknown"
        case_name = filepath.stem

        try:
            rel_path = filepath.relative_to(MARKDOWN_DIR.parent)
        except ValueError:
            rel_path = filepath

        print(f"[{i}/{len(files)}] {rel_path}")

        text = filepath.read_text(encoding="utf-8")
        if len(text) < 200:
            print(f"    [SKIP] Too short ({len(text)} chars)")
            stats["skipped"] += 1
            continue

        doc_name = f"{architect_name}_{case_name}.md"

        if dry_run:
            print(f"    [DRY RUN] Would upload: {doc_name} ({len(text)} chars)")
            stats["uploaded"] += 1
            continue

        result = upload_document(doc_name, text, ds_id, key)

        if result:
            doc_id = result.get("document", {}).get("id", "")
            batch = result.get("batch", "")
            print(f"    [OK] Uploaded (doc_id={doc_id}, batch={batch})")

            if doc_id:
                time.sleep(0.5)
                status = check_document_status(doc_id, ds_id, key)
                print(f"    [STATUS] Indexing: {status}")

            stats["uploaded"] += 1
            stats["results"].append({
                "file": str(rel_path),
                "document_id": doc_id,
                "batch": batch,
                "status": "uploaded",
            })
        else:
            print(f"    [FAIL] Upload failed")
            stats["failed"] += 1
            stats["results"].append({
                "file": str(rel_path),
                "status": "failed",
            })

        if i < len(files):
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\n{'='*50}")
    print(f"[SUMMARY]")
    print(f"{'='*50}")
    print(f"  Total: {stats['total']}")
    print(f"  Uploaded: {stats['uploaded']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")

    if stats["uploaded"] > 0:
        print(f"\n[TIP] Documents uploaded. Indexing may take a few minutes.")
        print(f"   Check Dify web UI -> Knowledge Base -> indexing progress")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ArchAI Dify Importer - Auto-upload Markdown to Dify Knowledge Base"
    )
    parser.add_argument("--dataset-id", help="Dify dataset ID (or set DIFY_DATASET_ID)")
    parser.add_argument("--api-key", help="Dify API Key (or set DIFY_API_KEY)")
    parser.add_argument("--architect", help="Filter by architect (e.g. 'Tadao Ando')")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, no actual upload")
    parser.add_argument("--base-url", default="", help="Override Dify API base URL")

    args = parser.parse_args()

    if args.base_url:
        DIFY_API_BASE = args.base_url

    import_all(
        dataset_id=args.dataset_id or "",
        api_key=args.api_key or "",
        architect_filter=args.architect or "",
        dry_run=args.dry_run,
    )
