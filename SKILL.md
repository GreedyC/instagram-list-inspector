---
name: instagram-list-inspector
description: Analyze user-accessible Instagram followers, following, and post/Reels likers in Codex's signed-in browser; compare accounts and posts, track dated changes, and produce evidence-aware reports.
---

# Instagram List Inspector (Codex)

Handle the analysis in this task, without the Followloom CLI, a ZIP export, pasted lists, or a copied session cookie. The user supplies only target handles/post URLs and the question. For operation definitions, the snapshot contract, and report rules, read [analysis-playbook.md](references/analysis-playbook.md) before analyzing or saving data.

## First-use orientation

On an explicit invocation such as `$instagram-list-inspector`, give a short orientation **before browser actions**, in the user's language. Cover what the user can ask, the minimum input, the only possible handoffs, and the default output. Keep it conversational, not a long questionnaire. If the invocation contains no concrete target/task, briefly cover these capabilities and ask one question:

- Mutual following and non-follow-backs for one account.
- Shared or distinct followers/following across accounts.
- Overlap between post/Reels likers and account audiences; repeat likers across posts.
- Dated additions/removals when earlier captures exist.
- In-chat findings by default, or a requested local HTML/CSV/JSON report.

Ask for only the target handle(s) or post/Reels URL(s) and the desired comparison. Do not ask for a password, cookie, ZIP export, or pasted lists. The user may need to complete Instagram login/verification or approve the browser's CDP access. A historical comparison needs an earlier capture; if none exists, offer to create a baseline. In Turkish, a concise friendly opening is appropriate; in other languages, match the user's tone.

If the user already supplied a complete request, condense this to one sentence (what will be compared and that no credential/export is needed), then proceed without asking them to pick from a menu. If only the target or the intended comparison is missing, ask for that one missing piece. Do not start collecting an unrelated account merely to demonstrate the skill. Do not promise a complete list before access and coverage are checked.

## Scope

Support all analytical features from the Followloom product plan when the necessary lists are accessible:

- One account: followers ∩ following (mutuals), followed-but-not-following-back, followers-not-followed-back.
- Two or more accounts: shared/unique followers or following, pairwise and three-way intersections, overlap with explicitly named denominators, and candidate audience bridges.
- A post or Reel: observed likers ∩ any selected account's followers/following; observed likers outside those lists; multiple posts' repeat-liker and campaign-overlap analysis.
- Dated captures: additions/removals between comparable snapshots, changes in intersections, and careful treatment of username changes or disappeared accounts.
- Evidence-aware output: coverage and source for every set, partial-data sensitivity, concise in-chat findings, and user-requested local JSON/CSV/HTML reports with aggregate-only or pseudonymous sharing options.

Do not confuse supported *analysis* with guaranteed data access. Instagram may withhold a list, limit a response, change a private web endpoint, or challenge the session. Never fill unavailable data by guessing, and never claim a negative observation from a partial list.

## Collect with minimum user effort

1. Resolve the requested targets from the user's message. Reuse a signed-in Instagram tab through the browser tool; ask only for missing handles/post URLs that cannot be inferred. The user handles login, verification, and any full-CDP approval. If browser/CDP access is unavailable, explain it; use the slower visible-UI fallback only if the user wants it.
2. Follow the browser tool's initialization and CDP capability documentation. Observe network events around opening the requested list once in the normal UI. Identify the actual same-origin list request and response; never assume an endpoint from an older run. Read only the fields needed for ID/handle matching, displayed/returned totals, and pagination.
3. If more pages are advertised, use the *same tab's existing session* for sequential, bounded, same-origin requests derived from that observed GET and its cursor. Keep necessary headers and tokens in memory only. Do not print, persist, export, or pass cookies, CSRF tokens, raw request URLs, or full network bodies to another service. Stop at a challenge, 429, access denial, cursor loop, malformed/empty page, or reasonable page cap; no bypass, proxy rotation, or aggressive retry.
4. For each list record its profile/post URL, kind, UTC capture time, displayed or response total, distinct stable IDs and current handles, pages read, pagination-end evidence, access/stop reason, and coverage status. Prefer stable IDs for joins; a handle-only match is provisional. Reconcile count with the source total, but do not treat a matching count alone as proof of full coverage.

Reinspect each list type's live request and response before relying on it. A successful capture from another session is not evidence that a new capture is complete.

## Analyze and deliver

Use [analysis-playbook.md](references/analysis-playbook.md) for exact set definitions, temporal conditions, partial-data language, report schema, and privacy defaults. Compute only from observed IDs/handles. Label every table/claim with capture times and coverage. Say “not observed in this capture” rather than “did not like,” “unfollowed,” or “has a relationship.” For a historical comparison, save dated local snapshots only when the user requests tracking or a report that requires them; tell the user the local path and do not put account lists in vault memory or a public repository.

Return the answer in chat by default. Generate local HTML/CSV/JSON only when requested; default any shareable report to aggregate results, with identities included only when the user asks. No auto-publishing, scheduled monitoring, mobile app, or CLI is implied by this skill.
