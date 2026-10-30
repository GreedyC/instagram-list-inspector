"""Tests for the official Meta Instagram export importer."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.import_export import build_capture, extract_members_from_meta_json

ROOT = Path(__file__).resolve().parents[1]


class ImportExportTests(unittest.TestCase):
    def test_extract_followers_array_format(self):
        sample = [
            {
                "title": "",
                "media_list_data": [],
                "string_list_data": [
                    {
                        "href": "https://www.instagram.com/user_alpha",
                        "value": "user_alpha",
                        "timestamp": 1729000000,
                    }
                ],
            },
            {
                "title": "",
                "media_list_data": [],
                "string_list_data": [
                    {
                        "href": "https://www.instagram.com/user_beta",
                        "value": "USER_BETA",
                        "timestamp": 1729001000,
                    }
                ],
            },
            {
                # Duplicate case variant
                "title": "",
                "media_list_data": [],
                "string_list_data": [
                    {
                        "href": "https://www.instagram.com/User_Alpha",
                        "value": "User_Alpha",
                        "timestamp": 1729002000,
                    }
                ],
            },
        ]
        members = extract_members_from_meta_json(sample)
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0], {"id": None, "username": "user_alpha"})
        self.assertEqual(members[1], {"id": None, "username": "user_beta"})

    def test_extract_following_object_format(self):
        sample = {
            "relationships_following": [
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": [
                        {
                            "href": "https://www.instagram.com/followed_one",
                            "value": "followed_one",
                            "timestamp": 1729003000,
                        }
                    ],
                }
            ]
        }
        members = extract_members_from_meta_json(sample)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["username"], "followed_one")

    def test_build_capture_produces_valid_v2_schema(self):
        members = [{"id": None, "username": "test_account"}]
        capture = build_capture("https://www.instagram.com/creator/", "followers", members)
        self.assertEqual(capture["schema_version"], 2)
        self.assertEqual(capture["source_url"], "https://www.instagram.com/creator/")
        self.assertEqual(capture["kind"], "followers")
        self.assertEqual(capture["displayed_total"], 1)
        self.assertEqual(capture["coverage"], "end_and_count_match")
        self.assertEqual(capture["identity_mode"], "handle_only_uncertain")
        self.assertEqual(len(capture["passes"]), 1)

    def test_cli_import_to_file(self):
        with tempfile.TemporaryDirectory() as directory:
            in_file = Path(directory) / "followers_1.json"
            out_file = Path(directory) / "capture.json"
            in_file.write_text(
                json.dumps(
                    [
                        {
                            "string_list_data": [
                                {
                                    "href": "https://www.instagram.com/fan_one",
                                    "value": "fan_one",
                                    "timestamp": 1729000000,
                                }
                            ]
                        }
                    ]
                ),
                encoding="utf-8",
            )
            cmd = [
                sys.executable,
                str(ROOT / "scripts/import_export.py"),
                "--file",
                str(in_file),
                "--kind",
                "followers",
                "--target-url",
                "https://www.instagram.com/myaccount/",
                "--output",
                str(out_file),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.exists())
            loaded = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], 2)
            self.assertEqual(loaded["members"][0]["username"], "fan_one")


if __name__ == "__main__":
    unittest.main()
