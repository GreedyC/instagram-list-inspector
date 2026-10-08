# Instagram audience analysis playbook

Read this reference when using `instagram-list-inspector`. The skill is an on-demand Codex workflow, not the Followloom CLI. Its full feature *coverage* is conditional on the actual Instagram lists being observable and on the user requesting the relevant targets or historical comparison.

## Normalized capture and coverage

Keep one record per source list. Use this shape for working data and any user-requested local snapshot; do not include browser headers or session material:

```json
{
  "schema_version": 2,
  "source_url": "https://www.instagram.com/example/",
  "kind": "followers",
  "captured_at_utc": "2026-09-24T12:00:00Z",
  "displayed_total": 114,
  "returned_total": null,
  "displayed_total_source": "profile",
  "returned_total_source": null,
  "pages_read": 11,
  "end_evidence": "no_next_cursor_and_has_more_false",
  "stop_reason": "normal_end",
  "coverage": "end_and_count_match",
  "identity_mode": "stable_id",
  "passes": [{
    "captured_at_utc": "2026-09-24T12:00:00Z",
    "pages_read": 11,
    "observed_count": 114,
    "displayed_total": 114,
    "returned_total": null,
    "displayed_total_source": "profile",
    "returned_total_source": null,
    "identity_mode": "stable_id",
    "members": [{"id": "platform-id-if-observed", "username": "example_handle"}],
    "end_evidence": "no_next_cursor_and_has_more_false",
    "stop_reason": "normal_end"
  }],
  "members": [{"id": "platform-id-if-observed", "username": "example_handle"}]
}
```

`kind` is `followers`, `following`, or `likers`. For likers, use the post/Reels URL as `source_url`. `displayed_total`/`returned_total` may be null. `coverage` is one of:

- `end_and_count_match`: explicit pagination end plus unique stable-ID count equal to a credible total.
- `count_match_no_end_signal`: stable-ID count matches a credible displayed/response total, but no explicit end signal exists.
- `observed_end_no_total`: stable-ID capture with explicit end and no credible total for reconciliation; provisional identity overrides this to `partial`.
- `partial`: a cap, challenge, error, cursor loop, count mismatch, known truncation or provisional identity prevents a strong completeness claim.
- `unknown`: no sound completeness judgment.

An Instagram count may change during collection or omit unavailable accounts. Even `end_and_count_match` is evidence for this capture, not a guarantee of a timeless complete list. Record whether a total came from the profile, post, or JSON response. Deduplicate by stable platform ID; if unavailable, normalize handles case-insensitively and mark matches `handle_only_uncertain`. Never infer a deleted account or a person's identity from a missing/renamed handle.

`identity_mode` is `stable_id`, `handle_only_uncertain`, or `mixed_uncertain`.
Use ID keys when observed, otherwise normalized-handle keys. Do not merge an
ID-bearing row and a handle-only row solely because their handles match; record
the uncertainty, and do not use mixed/provisional identity for strong absence
claims. A matching handle count does not establish stable account identity.
Handle-only or mixed captures remain `partial` even if their observed-key count
matches the total; retain the end/count evidence and report the provisional
match separately. Neither count-match coverage label applies to them.

`passes` contains one initial capture and, only if permitted below, one
consistency pass. Keep each pass's time, totals and their sources, identity mode,
members with the handles seen in that pass, observed distinct-key count, page
count, end evidence and stop reason separately. Total-source values are
`profile`, `post`, `response`, or null when no total was observed. The abbreviated
example shows one representative member; actual snapshots preserve every observed
member and counts must match those records. Top-level `pages_read` is
their sum; `members` is the deduplicated union, not the sum of pass counts.
Top-level time/totals/total-source/end/stop fields describe the final pass, never
a sum or a selected larger total; coverage describes the
whole capture. Conflicting totals or uncertain cross-pass identity retain
`partial`/`unknown`, not a forced count match. All conflicting totals remain in
their original pass records. Legacy version-1 snapshots retain their original
top-level summary and member records. Do not synthesize a pass, its membership,
timestamps or total sources from that summary: pass history is unknown. Infer
identity mode only from the saved members (all IDs, all handles, or mixed); do
not promote a legacy coverage label when identity/provenance is uncertain.
New snapshots use version 2; there is no automatic rewrite of legacy files.

### Count reconciliation

Pagination exhaustion does not always reconcile with the profile's displayed count. A list can end with fewer distinct identity keys (stable IDs when available, normalized handles otherwise) because of overlapping pages, unavailable accounts, changing membership, or a platform response that omits entries; do not assume which cause applies.

When `has_more` is false (or the cursor ends) but the distinct-key count is below a credible displayed/response total, including handle-only captures:

1. Record the mismatch and keep coverage as `partial`. Check whether the request, response, or page sequence explicitly signals a limit, hidden entries, errors, duplicate IDs, or a changing total. Do not infer that the unobserved accounts are a particular person.
2. If the session is healthy and the observed GET already has a page-size parameter, at most **one** additional, sequential consistency pass may use a moderate larger page size accepted by the same endpoint. Keep the same origin, current signed-in tab, normal pacing, and stop conditions. Do not use repeated passes to force a count match, parallelize requests, or work around a limit/challenge. If there is no observed page-size parameter, do not invent an endpoint or parameter.
3. Union the two passes by stable ID, or by normalized handle when IDs are absent; handle-only matches remain provisional. Keep the later handle only for the same observed stable ID. Record both passes in `passes`, preserving members, page counts and end evidence. A second pass may find additional identity keys without explaining the discrepancy. Mark `end_and_count_match` only for stable-ID captures when an explicit end signal and distinct-ID count genuinely match a consistent credible total; otherwise retain `partial` and report `observed / displayed` counts. Do not infer identity across renames or fill in missing IDs.

For intersections, every reported common ID must be present in both observed sets. If either set remains partial, call the result “at least N observed common accounts”; do not state that there are exactly N in the full lists or that no others exist. Avoid a false precision percentage based on displayed totals.

If the user requests tracking or a report requiring historical comparison, save snapshots by default under the user's private application-data directory (`~/Library/Application Support/instagram-list-inspector/snapshots` on macOS, or the platform's corresponding user-data directory); honor a specified location instead. Do not ask the user to choose a path merely for convenience. Keep the directory outside any public Git repository and restrict access to the user when the filesystem supports it. Save only normalized records. Do not silently overwrite an earlier capture: include timestamp and source identity in the name. For a historical question without an older saved capture, report that a baseline is missing and offer to save today's capture; do not fabricate a past state.

## Exact analyses

All set operations below use stable IDs when both sides have them. Let `F_A` = followers of account A, `G_A` = accounts followed by A, `L_P` = observed likers of post P. If ID availability differs, segregate certain ID matches from provisional handle matches.

| Request | Calculation | Report label / caveat |
| --- | --- | --- |
| Mutual following | `F_A ∩ G_A` | Mutuals observed at capture times. |
| A follows, no follow-back observed | `G_A − F_A` | Confirmed absence only if `F_A` coverage is sound; otherwise “not observed among captured followers.” |
| Follows A, A does not follow | `F_A − G_A` | Same rule for `G_A` coverage. |
| Two-account common audience | `F_A ∩ F_B`, or requested `G` lists | Show common, A-only, B-only, both timestamps and coverage. |
| Three or more accounts | intersection/union across all named lists | Show all-way intersection, each account's unique observed members, and relevant pairwise intersections. |
| Audience bridges | members in multiple selected audiences, optionally absent from another | Label a set pattern, not a personal relationship or true reach estimate. |
| Post/Reels × audience | `L_P ∩ F_A`, `L_P ∩ G_A`, `L_P − F_A` | “Observed liker not in follower capture”; never “liked then unfollowed” without dated evidence. |
| Campaign repeat | per-ID number of posts liked among observed `L_P` sets | Show repeat-liker count/frequency and overlap; incomplete liker lists bias absence and rates. |
| Time change | newer minus older, older minus newer for same account and same kind | “Newly observed” / “present earlier, absent later.” Complete captures needed for strong absence; no automatic unfollow attribution. |
| Intersection change | compare intersection sets from two aligned time windows | Name every underlying list and timestamp; unequal time windows can create apparent changes. |

For two sets, if coverage supports a rate, report both Jaccard `|A∩B| / |A∪B|` and the directional shares `|A∩B| / |A|` and `/ |B|`, with denominators named. Do not call any of these “incremental reach.” If a list is partial, numbers are **observed-set statistics**, not true audience percentages. Avoid a percentage when the user could mistake it for full coverage.

For partial-data sensitivity, show how a conclusion might move under missing-member assumptions. If both displayed totals are credible, at least the observed members truly belong to their lists, and `N_A≥|O_A|`, `N_B≥|O_B|`, let `K=|O_A∩O_B|`, `x=N_A−|O_A|`, `y=N_B−|O_B|`. A conservative overlap envelope is `K ≤ |A∩B| ≤ min(N_A,N_B,K+x+y)`; label it a loose mathematical bound, not a probability or platform guarantee. Without trustworthy totals, provide qualitative scenarios only. Never infer why an account disappeared: rename, deactivation, blocking, access change, and real unfollow are alternatives. Like timestamps are not established merely by inclusion in a current liker list.

## Report behavior

Default in-chat report: question, observed result, relevant handles only if useful/requested, source URLs, capture times, each list's observed/total count and coverage, assumptions, and what cannot be concluded. If the user asks for a file without naming a destination, use a private `reports` sibling to the default `snapshots` directory above and return a clickable local path. A user-requested local report may include:

- JSON: normalized captures plus derived operations and evidence metadata.
- CSV: one row per derived membership/overlap with `analysis`, `source`, `captured_at_utc`, `platform_id` (only in private full reports), `username` (only if requested), and `coverage`.
- HTML: readable summary, source/evidence table, chosen comparisons, warnings, and optional compact overlap diagram or table. Escape all user-supplied handles/text before rendering.

Private reports may include handles when the user requests them. A report intended for sharing defaults to aggregate counts and no raw handles/IDs. If pseudonyms are requested, use fresh per-report labels (e.g. `Person 001`) without embedding a reversible mapping or stable cross-report hash in the shared file. Keep any mapping local only if explicitly needed. Never put session data, raw request URLs, third-party account lists, or private report content in the skill, vault memory, git, or public links. Do not upload or publish a report unless specifically requested.

Do not create a scheduled monitor from a request for historical analysis. A future scheduled check requires a separate explicit user request and must still respect browser/session availability and platform limits.
