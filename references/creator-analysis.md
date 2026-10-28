# Creator comparisons and local interactive reports

Use this reference for content-topic comparisons, commenters × post likers ×
audiences, common questions in observed comments, or a clickable report. The
agent performs browser/computer use. `scripts/creator_report.py` only validates
normalized observations and computes results; it has no network, login or
collection capability. Do not ask the user to install/run a CLI or supply lists.

## Observe the requested sources

- Resolve the posts and question first. Ask for missing post URLs or topic labels
  only when needed. Use the user's labels (e.g. Coffee/Coding), or classify visible
  post content only if the user delegates that choice. Do not invent labels from
  a participant's appearance, language, or presumed personal attributes.
- Follow the actual client tool documentation. With computer use, open the
  normal post/Reel UI, read visible comment authors, then use its load-more/reply
  controls in bounded steps. Match the author link, not an @mention inside a
  comment. Do not switch to hidden endpoints in a UI-only task. The existing
  optional network route applies only when the current tool explicitly permits it.
- Recheck that the requested list dialog is still open after navigation or
  scrolling. Read usernames from the visible author/profile link, excluding
  verification badges or display names. Captions by the post owner are not
  comment records; an unavailable comment control is not an empty comment list.
- Read the post's liker list separately. Likes on an individual comment are not
  likes on the post. Followers/following are additional requested sources, not
  prerequisites for a simple post comparison.
- State whether comments cover `top_level`, `top_level_and_replies`, or only a
  `visible_subset`. Unopened replies/hidden comments remain unobserved. A challenge,
  limit, repeated rows or lack of movement means stop with partial/unknown coverage.
- A displayed comment total counts comment records, **not unique commenters**.
  Keep it in `displayed_comment_total`. Leave commenter `displayed_total` and
  `returned_total` null. Do not claim full-author coverage from that counter.
- Prefer observed comment IDs to deduplicate comment records. If unavailable,
  retain author observations and mark rows without IDs; do not invent comment IDs
  or an exact unique-comment count. Within one capture, resolve repeated rows from source evidence; the helper rejects a handle that appears both with an ID and as a handle-only record instead of silently counting it twice. Never substitute collection time for posting time.

If the user asks what questions/themes appear in comments, the agent can group
the actually observed comment text and report neutral aggregate themes. Read
text only for that requested analysis; do not include it in normalized files or
exported reports. Count observed records and retain their source keys. Do not
present themes as a population estimate, sentiment diagnosis or participant trait.
If text/replies are unavailable, say so instead of generating plausible themes.

## Normalized helper input

Python 3.10+ with the standard library is sufficient. Locate the helper relative
to this installed skill. The following bundle wraps the existing capture format;
its bundle version is independent of the version-2 single-capture snapshot
contract in the main playbook. This helper accepts only the documented fields
below: keep reconciliation pass history in the private snapshot and supply its
resolved members, final timestamp/counts and conservative coverage here. Do not
pass a version-2 snapshot directly or discard unresolved provenance to claim
complete coverage.

```json
{
  "schema_version": 1,
  "title": "Observed participation by content topic",
  "question": "Compare these selected posts, not total reach.",
  "captures": [
    {
      "key": "post-a-likes",
      "source_url": "https://www.instagram.com/p/SYNTH_A/",
      "kind": "likers",
      "topic": "Coffee",
      "captured_at_utc": "2026-10-22T12:00:00Z",
      "coverage": "partial",
      "displayed_total": 10,
      "end_evidence": "not_observed",
      "stop_reason": "user_stopped",
      "members": [{"id": "90000000001", "username": "synthetic_one"}]
    },
    {
      "key": "post-a-comments",
      "source_url": "https://www.instagram.com/p/SYNTH_A/",
      "kind": "commenters",
      "topic": "Coffee",
      "captured_at_utc": "2026-10-22T12:01:00Z",
      "coverage": "partial",
      "displayed_total": null,
      "displayed_comment_total": 8,
      "comment_scope": "visible_subset",
      "end_evidence": "not_observed",
      "stop_reason": "replies_not_opened",
      "comments": [
        {"id": "synthetic-comment-1", "author": {"id": "90000000001", "username": "synthetic_one"}, "is_reply": false}
      ]
    }
  ],
  "comment_themes": [
    {"label": "A preparation question (synthetic)", "observed_count": 1, "source_keys": ["post-a-comments"]}
  ]
}
```

Use capture timestamps in `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` format or with an
explicit `±HH:MM` offset. Fractions may have one to six digits; finer precision is
rejected rather than silently rounded. Timestamps are normalized to UTC.

Use canonical HTTPS Instagram profile/post URLs without query strings, credentials
or fragments. Keys must be unique. Within a capture, conflicting labels for the same ID must be normalized from
source evidence or the ambiguous username omitted. Case differences and missing
labels do not conflict; name changes across different captures remain supported.
Select one capture per source/kind, with the
same topic for a post's liker/commenter sources. For dated questions, first select
the intended comparable captures; this helper rejects silently mixing repeated
snapshots of the same list into one creator comparison.

`members` contains normalized accounts. Commenters can instead/additionally supply
`comments` records with `id` (omit when not observed), `author`, and `is_reply`.
Only these fields are accepted: comment text, headers, cookies and session
material are not helper input. No claim of complete coverage is inferred from a
page ending alone. Count/end mismatches and handle-only observations downgrade or
qualify the evidence. A capture spread over 24 hours is explicitly flagged.

## Run inside the agent workflow

Feed the normalized JSON through stdin where possible, without printing session
material or persisting lists into the skill repository. For a file already
requested by the user, choose a timestamped private path as in the main playbook.

```text
python <skill-dir>/scripts/creator_report.py --input -
python <skill-dir>/scripts/creator_report.py --input <private-input.json> --html <private-report.html> --language tr
```

No output option returns an aggregate JSON model for the agent's in-chat answer.
`--html` and `--json` create a requested export. The helper never overwrites a
previous file; choose a new timestamped name. New output files are user-only where
supported. Default `--identity-mode aggregate` omits participant IDs and handles
from membership lists in the **entire** export, including embedded HTML data. Requested source URLs and descriptive metadata remain visible. Use neutral titles, questions, source keys, topic/theme labels and stop notes for a shareable report: the helper cannot recognize or redact personal information in arbitrary prose. Do not put participant names, raw comment quotations or session material in these fields. Use `pseudonymous` for
fresh report-local aliases or `identified` only when the user asks to include
participant identities. `--language en|tr` selects report controls; preserve the
user's language in the title/question/labels. For other languages, explain the
report-control language and keep the chat response in the user's language.

If code execution/Python is unavailable in the current client, the agent can do
small set comparisons in chat using these definitions, but must not claim to have
generated or validated a report file. Skill installation alone enables no tools.

## What the calculations mean

- Stable-ID intersections are certain **observed** matches. Same handles with
  missing IDs are possible matches shown separately; different observed IDs with
  the same handle never become an automatic match.
- A post's participants are the union of its observed likers/commenters. An
  account that both likes and comments counts once in that post. Missing liker or
  commenter collection is `null`/“not collected”, never an empty list.
- Topic known-account totals deduplicate IDs across distinct posts. “Repeat”
  requires at least two posts, not two comments or a like plus comment on one post.
  Possible repeated handles are counted separately for UI-only observations;
  conflicting observed IDs never turn into a provisional repeat.
  “Only in this topic here” means not observed in other supplied topics. It does
  not mean a new follower, new viewer, or incremental reach.
- Topic comparisons name their post counts and show handle-only observations
  separately. Different capture windows, post selection, and incomplete coverage
  prevent claims that a topic caused growth or is a definitive winner.
- Optional follower/following captures support post-participant × audience
  intersections. “Liker ID not observed among commenters” is an observation, not
  proof of no comment when either source is partial or identity availability differs.

## Clickable report behavior

The self-contained HTML works offline and makes no network requests. Search,
topic/date filters and sorting narrow the **post table only**; date filters use
each post's latest capture timestamp in UTC, not its publication date. The topic
table remains clearly labelled as whole-report totals, avoiding false unique
counts from summed filtered post counts. For a different topic-analysis window,
select the captures and regenerate through the agent.

Open a post's “View evidence” disclosure for source timestamps, scope, counts,
end evidence, provisional matches and requested identity detail. Every input is
rendered as text; unknown/partial data, no results and invalid date ranges have
explicit states. The source evidence section includes audience capture times too.

For developer verification, `tests/fixtures/creator-observations.json` is entirely
synthetic. `python -m unittest discover -s tests -v` checks the real helper behavior.
Synthetic reports are demonstrations, not evidence of live Instagram collection.
