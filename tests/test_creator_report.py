"""Behavioral checks on synthetic observations, never live account data."""

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.creator_report import (
    InputError,
    analyze,
    render_csv,
    render_report,
    timestamp,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/creator-observations.json"


class CreatorAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_deduplicates_accounts_comments_and_same_post_participation(self):
        model = analyze(self.bundle)
        first = model["posts"][0]
        self.assertEqual((first["likers"], first["commenters"]), (3, 3))
        self.assertEqual(first["both"]["known_count"], 1)
        self.assertEqual(first["both"]["possible_handle_count"], 1)
        self.assertEqual(first["known_accounts"], 3)
        comments = next(s for s in first["sources"] if s["kind"] == "commenters")
        self.assertEqual(comments["identified_comment_count"], 3)
        self.assertEqual(comments["displayed_comment_total"], 9)
        self.assertEqual(comments["observed_accounts"], 3)

    def test_topics_count_repeat_accounts_across_distinct_posts(self):
        model = analyze(self.bundle)
        topics = {t["topic"]: t for t in model["topics"]}
        self.assertEqual(topics["Coffee"]["posts"], 2)
        self.assertEqual(topics["Coffee"]["known_accounts"], 4)
        self.assertEqual(topics["Coffee"]["repeat_known_accounts"], 1)
        self.assertEqual(topics["Coffee"]["only_observed_in_topic"], 3)
        self.assertEqual(model["topic_overlap"][0]["known_count"], 1)

    def test_ui_only_handles_support_provisional_repeats_without_fake_id_matches(self):
        self.bundle["captures"][2]["members"].append({"username": "synthetic_ui_only"})
        self.bundle["captures"][2]["displayed_total"] = 3
        topics = {t["topic"]: t for t in analyze(self.bundle)["topics"]}
        self.assertEqual(topics["Coffee"]["possible_repeat_handles"], 1)
        self.assertEqual(topics["Coffee"]["repeat_known_accounts"], 1)

    def test_conflicting_labels_within_one_capture_are_not_silently_overwritten(self):
        self.bundle["captures"][2]["members"].append(
            {"id": "90000000001", "username": "different_handle"}
        )
        with self.assertRaisesRegex(InputError, "conflicting labels"):
            analyze(self.bundle)

    def test_case_variants_and_missing_handle_do_not_conflict(self):
        self.bundle["captures"][2]["members"].extend(
            [{"id": "90000000001", "username": "SYNTHETIC_ONE"}, {"id": "90000000001"}]
        )
        self.assertEqual(analyze(self.bundle)["posts"][1]["likers"], 2)

    def test_dot_segments_are_not_canonical_accounts(self):
        for handle in [".", ".."]:
            bundle = copy.deepcopy(self.bundle)
            bundle["captures"][0]["members"] = [{"username": handle}]
            with self.assertRaises(InputError):
                analyze(bundle)
            bundle = copy.deepcopy(self.bundle)
            bundle["captures"][-1]["source_url"] = (
                f"https://www.instagram.com/{handle}/"
            )
            with self.assertRaises(InputError):
                analyze(bundle)

    def test_different_ids_with_the_same_handle_are_not_matched(self):
        coding = analyze(self.bundle)["posts"][2]
        self.assertEqual(coding["both"]["known_count"], 0)
        self.assertEqual(coding["both"]["possible_handle_count"], 0)

    def test_missing_list_is_not_an_empty_collected_list(self):
        post = analyze(self.bundle)["posts"][1]
        self.assertIsNone(post["commenters"])
        self.assertIsNone(post["both"])
        self.assertIsNone(post["like_not_observed_comment"])
        source = analyze(self.bundle)["posts"][2]["sources"][1]
        self.assertIsNone(source["identified_comment_count"])

    def test_audience_overlap_and_provisional_matches_remain_separate(self):
        post = analyze(self.bundle)["posts"][0]
        self.assertEqual(post["audiences"][0]["overlap"]["known_count"], 1)
        self.assertEqual(post["audiences"][0]["kind"], "followers")

    def test_false_complete_status_is_downgraded(self):
        source = analyze(self.bundle)["sources"][0]
        self.assertEqual(source["coverage"], "partial")
        self.assertTrue(
            any("does not match" in w for w in analyze(self.bundle)["warnings"])
        )

    def test_complete_status_requires_id_count_end_and_normal_stop(self):
        for update in [
            {"end_evidence": "not_observed"},
            {"stop_reason": "challenge"},
            {"displayed_total": None},
            {"returned_total": 99},
        ]:
            bundle = copy.deepcopy(self.bundle)
            bundle["captures"][2].update(update)
            source = analyze(bundle)["sources"][2]
            self.assertEqual(source["coverage"], "partial")

    def test_comment_counter_is_never_used_as_an_author_counter(self):
        self.bundle["captures"][1]["displayed_total"] = 9
        with self.assertRaisesRegex(InputError, "totals must be null"):
            analyze(self.bundle)

    def test_observed_comment_records_exceeding_the_counter_are_qualified(self):
        self.bundle["captures"][1].update(
            displayed_comment_total=1, coverage="observed_end_no_total"
        )
        model = analyze(self.bundle)
        self.assertEqual(model["sources"][1]["coverage"], "partial")
        self.assertTrue(any("comment counter disagree" in w for w in model["warnings"]))

    def test_end_without_total_is_not_reported_as_complete_post_evidence(self):
        model = analyze(self.bundle)
        self.assertEqual(model["posts"][2]["coverage"], "limited_evidence")
        self.assertTrue(any("lack verified complete" in w for w in model["warnings"]))

    def test_mixed_id_and_handle_only_duplicates_in_one_capture_are_rejected(self):
        self.bundle["captures"][2]["members"].append({"username": "synthetic_one"})
        with self.assertRaisesRegex(InputError, "mixes ID and handle-only"):
            analyze(self.bundle)

    def test_comment_scope_and_id_conflicts_are_rejected(self):
        for change in ["scope", "author"]:
            bundle = copy.deepcopy(self.bundle)
            capture = bundle["captures"][1]
            if change == "scope":
                capture["comment_scope"] = "top_level"
            else:
                capture["comments"][2]["author"]["id"] = "different"
            with self.assertRaises(InputError):
                analyze(bundle)

    def test_comment_rows_without_ids_have_no_claimed_unique_count(self):
        self.bundle["captures"][1]["comments"].append(
            {"author": {"username": "synthetic_extra"}}
        )
        source = analyze(self.bundle)["sources"][1]
        self.assertEqual(source["identified_comment_count"], 3)
        self.assertEqual(source["unidentified_comment_rows"], 1)

    def test_aggregate_and_pseudonymous_exports_omit_account_and_comment_ids(self):
        for mode in ["aggregate", "pseudonymous"]:
            model = analyze(self.bundle, mode)
            output = json.dumps(model) + render_report(model)
            for capture in self.bundle["captures"]:
                for member in capture.get("members", []):
                    for value in member.values():
                        self.assertNotIn(value, output)
                for comment in capture.get("comments", []):
                    self.assertNotIn(comment["id"], output)
                    for value in comment["author"].values():
                        self.assertNotIn(value, output)
        self.assertEqual(analyze(self.bundle)["posts"][0]["accounts"], [])
        self.assertTrue(analyze(self.bundle, "pseudonymous")["posts"][0]["accounts"])

    def test_identified_mode_includes_latest_observed_handle(self):
        self.bundle["captures"][1]["captured_at_utc"] = "2026-10-22T15:00:00Z"
        model = analyze(self.bundle, "identified")
        self.assertIn("@synthetic_renamed", model["posts"][0]["both"]["accounts"])

    def test_untrusted_topic_and_title_cannot_close_script_or_add_markup(self):
        payload = '</script><img src=x onerror="window.injected=true">'
        self.bundle["title"] = payload
        for capture in self.bundle["captures"][:2]:
            capture["topic"] = payload
        document = render_report(analyze(self.bundle))
        self.assertNotIn(payload, document)
        self.assertIn("connect-src 'none'", document)
        self.assertNotIn("__REPORT_DATA__", document)

    def test_user_text_is_not_reinterpreted_as_template_tokens(self):
        self.bundle["title"] = "Literal __REPORT_DATA__ and __NONCE__"
        model = analyze(self.bundle)
        document = render_report(model)
        self.assertIn("<title>Literal __REPORT_DATA__ and __NONCE__</title>", document)
        payload = (
            document.split('id="report-data"', 1)[1]
            .split(">", 1)[1]
            .split("</script>", 1)[0]
        )
        self.assertEqual(json.loads(payload)["title"], self.bundle["title"])

    def test_raw_session_material_and_comment_text_are_not_accepted(self):
        for where, key in [
            (self.bundle, "cookies"),
            (self.bundle["captures"][0], "headers"),
            (self.bundle["captures"][1]["comments"][0], "text"),
        ]:
            where[key] = "not-for-export"
            with self.assertRaises(InputError):
                analyze(self.bundle)
            del where[key]

    def test_urls_cannot_contain_credentials_queries_or_non_instagram_hosts(self):
        for url in [
            "https://evil.example/p/SYNTH/",
            "https://www.instagram.com/p/SYNTH/?token=x",
            "javascript:alert(1)",
            "https://user@www.instagram.com/p/SYNTH/",
            "https://www.instagram.com/api/v1/friendships/",
            "https://www.instagram.com:443/p/SYNTH/",
        ]:
            self.bundle["captures"][0]["source_url"] = url
            with self.assertRaises(InputError):
                analyze(self.bundle)

    def test_invalid_shapes_duplicate_sources_and_topic_conflicts_are_rejected(self):
        for case in ["kind", "coverage", "duplicate", "topic", "negative"]:
            bundle = copy.deepcopy(self.bundle)
            if case == "kind":
                bundle["captures"][0]["kind"] = []
            elif case == "coverage":
                bundle["captures"][0]["coverage"] = {}
            elif case == "duplicate":
                bundle["captures"].append(copy.deepcopy(bundle["captures"][0]))
            elif case == "topic":
                bundle["captures"][1]["topic"] = "Different"
            else:
                bundle["captures"][0]["displayed_total"] = -1
            with self.assertRaises(InputError):
                analyze(bundle)

    def test_naive_dates_rejected_and_fractional_order_preserved(self):
        with self.assertRaises(InputError):
            timestamp("2026-10-22T12:00:00")
        self.assertLess(
            timestamp("2026-10-22T12:00:00Z"), timestamp("2026-10-22T12:00:00.1Z")
        )
        self.assertEqual(
            timestamp("2026-10-22T15:00:00+03:00"), timestamp("2026-10-22T12:00:00Z")
        )

    def test_timestamp_fraction_lengths_and_offset_rollover(self):
        for digits in range(1, 7):
            fraction = "123456"[:digits]
            with self.subTest(digits=digits):
                self.assertEqual(
                    timestamp(f"2026-10-22T00:00:00.{fraction}+03:00"),
                    f"2026-10-21T21:00:00.{fraction.ljust(6, '0')}Z",
                )
        for invalid in [
            "2026-10-22T12:00:00.1234567Z",
            "2026-10-22T12:00:00.Z",
            "2026-02-30T12:00:00Z",
            "2026-10-22T25:00:00Z",
            "2026-10-22T12:00:00+24:00",
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(InputError):
                timestamp(invalid)

    def test_end_without_total_respects_identity_and_stop_evidence(self):
        for change in ["handle_only", "interrupted", "total_present", "valid"]:
            bundle = copy.deepcopy(self.bundle)
            capture = bundle["captures"][2]
            capture.update(
                coverage="observed_end_no_total",
                displayed_total=None,
                returned_total=None,
                end_evidence="visible_end",
                stop_reason="normal_end",
            )
            if change == "handle_only":
                capture["members"] = [{"username": "synthetic_ui_only"}]
            elif change == "interrupted":
                capture["stop_reason"] = "challenge"
            elif change == "total_present":
                capture["displayed_total"] = len(capture["members"])
            with self.subTest(change=change):
                normalized = next(
                    c for c in analyze(bundle)["sources"] if c["key"] == capture["key"]
                )
                self.assertEqual(
                    normalized["coverage"],
                    "observed_end_no_total" if change == "valid" else "partial",
                )

    def test_non_simultaneous_captures_are_labelled(self):
        self.bundle["captures"][0]["captured_at_utc"] = "2026-10-19T12:00:00Z"
        self.assertTrue(any("24 hours" in w for w in analyze(self.bundle)["warnings"]))

    def test_themes_require_record_evidence_and_valid_source_keys(self):
        self.bundle["comment_themes"][0]["observed_count"] = 999
        with self.assertRaisesRegex(InputError, "exceeds observed"):
            analyze(self.bundle)
        self.bundle["comment_themes"][0]["observed_count"] = 1
        self.bundle["comment_themes"][0]["source_keys"] = ["a-likes"]
        with self.assertRaises(InputError):
            analyze(self.bundle)

    def test_agent_helper_works_from_stdin_and_does_not_overwrite_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            command = [
                sys.executable,
                str(ROOT / "scripts/creator_report.py"),
                "--input",
                "-",
                "--html",
                str(report),
                "--language",
                "tr",
            ]
            result = subprocess.run(
                command,
                check=False,
                input=json.dumps(self.bundle),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<html lang="tr">', report.read_text())
            original = report.read_bytes()
            result = subprocess.run(
                command,
                check=False,
                input=json.dumps(self.bundle),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(original, report.read_bytes())
            if sys.platform != "win32":
                self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_post_and_reel_formats_are_classified_correctly(self):
        model = analyze(self.bundle)
        post_formats = [p["format"] for p in model["posts"]]
        self.assertIn("post", post_formats)
        reel_capture = copy.deepcopy(self.bundle["captures"][0])
        reel_capture["key"] = "coffee_reel_likes"
        reel_capture["source_url"] = "https://www.instagram.com/reel/Ctest123/"
        self.bundle["captures"].append(reel_capture)
        model_with_reel = analyze(self.bundle)
        reel_posts = [p for p in model_with_reel["posts"] if p["format"] == "reel"]
        self.assertEqual(len(reel_posts), 1)
        self.assertEqual(reel_posts[0]["source_url"], "https://www.instagram.com/reel/Ctest123/")

    def test_csv_export_in_aggregate_mode_omits_identities(self):
        model = analyze(self.bundle, "aggregate")
        text = render_csv(model)
        rows = list(csv.reader(text.splitlines()))
        self.assertGreaterEqual(len(rows), 2)
        headers = rows[0]
        self.assertEqual(
            headers,
            [
                "topic",
                "format",
                "source_url",
                "captured_at_utc",
                "coverage",
                "likers",
                "commenters",
                "both_matched_by_id",
                "possible_handle_matches",
                "like_not_observed_comment",
                "comment_not_observed_like",
                "known_accounts",
                "handle_only_accounts",
            ],
        )
        self.assertNotIn("accounts", headers)
        self.assertNotIn("synthetic_one", text)
        self.assertNotIn("90000000001", text)

    def test_csv_export_in_pseudonymous_and_identified_modes(self):
        pseudonymous_csv = render_csv(analyze(self.bundle, "pseudonymous"))
        pseudo_rows = list(csv.reader(pseudonymous_csv.splitlines()))
        self.assertIn("accounts", pseudo_rows[0])
        self.assertTrue(any("Account " in cell for row in pseudo_rows[1:] for cell in row))
        self.assertNotIn("synthetic_one", pseudonymous_csv)

        identified_csv = render_csv(analyze(self.bundle, "identified"))
        ident_rows = list(csv.reader(identified_csv.splitlines()))
        self.assertIn("accounts", ident_rows[0])
        self.assertIn("@synthetic_one", identified_csv)

    def test_agent_helper_supports_csv_output_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            report_csv = Path(directory) / "report.csv"
            command = [
                sys.executable,
                str(ROOT / "scripts/creator_report.py"),
                "--input",
                "-",
                "--csv",
                str(report_csv),
            ]
            result = subprocess.run(
                command,
                check=False,
                input=json.dumps(self.bundle),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(report_csv.exists())
            self.assertTrue(report_csv.read_text(encoding="utf-8").startswith("topic,format,source_url,"))

            # Second run with same path must fail with code 2 without overwriting
            result2 = subprocess.run(
                command,
                check=False,
                input=json.dumps(self.bundle),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result2.returncode, 2)


if __name__ == "__main__":
    unittest.main()
