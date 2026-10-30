"""Convert official Instagram data download JSON files into normalized captures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_members_from_meta_json(data: dict | list) -> list[dict[str, str | None]]:
    """Extract normalized account members from Meta's followers/following JSON format."""
    entries = []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        if "relationships_following" in data:
            entries = data["relationships_following"]
        elif "relationships_followers" in data:
            entries = data["relationships_followers"]
        elif "string_list_data" in data:
            entries = [data]
        else:
            for val in data.values():
                if isinstance(val, list):
                    entries = val
                    break

    handles = set()
    members = []
    for item in entries:
        string_list = item.get("string_list_data", []) if isinstance(item, dict) else []
        for entry in string_list:
            if not isinstance(entry, dict):
                continue
            username = entry.get("value") or entry.get("href", "").rstrip("/").split("/")[-1]
            if not username:
                continue
            username = username.strip().lower()
            if re.fullmatch(r"[A-Za-z0-9._]{1,30}", username) and username not in {".", ".."}:
                if username not in handles:
                    handles.add(username)
                    members.append({"id": None, "username": username})

    members.sort(key=lambda m: m["username"])
    return members


def build_capture(source_url: str, kind: str, members: list[dict[str, str | None]]) -> dict:
    """Build a version-2 normalized capture record from extracted members."""
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    count = len(members)
    return {
        "schema_version": 2,
        "source_url": source_url.rstrip("/") + "/",
        "kind": kind,
        "captured_at_utc": now_utc,
        "displayed_total": count,
        "returned_total": count,
        "displayed_total_source": "official_export",
        "returned_total_source": "official_export",
        "pages_read": 1,
        "end_evidence": "official_data_export_complete",
        "stop_reason": "normal_end",
        "coverage": "end_and_count_match",
        "identity_mode": "handle_only_uncertain",
        "passes": [
            {
                "captured_at_utc": now_utc,
                "pages_read": 1,
                "observed_count": count,
                "displayed_total": count,
                "returned_total": count,
                "displayed_total_source": "official_export",
                "returned_total_source": "official_export",
                "identity_mode": "handle_only_uncertain",
                "members": members,
                "end_evidence": "official_data_export_complete",
                "stop_reason": "normal_end",
            }
        ],
        "members": members,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="path to official Meta JSON export file")
    parser.add_argument(
        "--kind",
        choices=["followers", "following"],
        required=True,
        help="list kind",
    )
    parser.add_argument(
        "--target-url",
        required=True,
        help="Instagram profile URL (e.g. https://www.instagram.com/myaccount/)",
    )
    parser.add_argument(
        "--output",
        help="output path for normalized capture JSON (defaults to stdout)",
    )
    args = parser.parse_args()

    try:
        raw_text = Path(args.file).expanduser().read_text(encoding="utf-8")
        data = json.loads(raw_text)
        members = extract_members_from_meta_json(data)
        capture = build_capture(args.target_url, args.kind, members)
        payload = json.dumps(capture, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            out_path = Path(args.output).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return 0
    except Exception as exc:
        print(f"Error converting official export: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
