"""Analyze normalized observations supplied by the agent; never access Instagram."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import secrets
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

COVERAGE = {
    "end_and_count_match",
    "count_match_no_end_signal",
    "observed_end_no_total",
    "partial",
    "unknown",
}
KINDS = {"followers", "following", "likers", "commenters"}
CAPTURE_FIELDS = {
    "key",
    "kind",
    "source_url",
    "captured_at_utc",
    "coverage",
    "members",
    "displayed_total",
    "returned_total",
    "pages_read",
    "end_evidence",
    "stop_reason",
    "topic",
    "comment_scope",
    "comments",
    "displayed_comment_total",
}


class InputError(ValueError):
    """A normalized input violates the documented observation contract."""


def require(condition, message):
    if not condition:
        raise InputError(message)


def fields(value, allowed, label):
    require(isinstance(value, dict), f"{label} must be an object")
    require(not set(value) - allowed, f"{label} contains unsupported fields")


def text(value, label, limit=500):
    require(
        isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
        f"{label} must be a nonempty string of at most {limit} characters",
    )
    return value.strip()


def count(value, label):
    require(
        value is None or (type(value) is int and value >= 0),
        f"{label} must be null or a nonnegative integer",
    )
    return value


def timestamp(value):
    value = text(value, "capture timestamp", 64)
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})",
        value,
    )
    require(
        match is not None,
        "capture timestamp must include seconds, a timezone and at most six fractional digits",
    )
    seconds, fraction, offset = match.groups()
    # Python 3.10 accepts only three or six fractional digits. Normalize before
    # parsing so every supported version preserves the same microsecond value.
    normalized = seconds + ("." + fraction.ljust(6, "0") if fraction else "")
    normalized += "+00:00" if offset == "Z" else offset
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InputError("capture timestamp must be ISO 8601 with a timezone") from exc
    require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        "capture timestamp must include a timezone",
    )
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def source_url(value, kind):
    value = text(value, "source URL", 300)
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "https"
            and url.netloc in {"instagram.com", "www.instagram.com"}
            and not url.query
            and not url.fragment
        )
    except ValueError as exc:
        raise InputError("invalid source URL") from exc
    pattern = (
        r"/(?:p|reel)/[A-Za-z0-9_-]+/?"
        if kind in {"likers", "commenters"}
        else r"/[A-Za-z0-9._]{1,30}/?"
    )
    require(
        valid and re.fullmatch(pattern, url.path) is not None,
        "use a canonical HTTPS Instagram profile/post URL without query, fragment or credentials",
    )
    path = url.path.rstrip("/")
    if kind in {"followers", "following"}:
        require(path not in {"/.", "/.."}, "a dot-segment is not a profile URL")
        path = path.lower()
    return "https://www.instagram.com" + path + "/"


def actor(value):
    fields(value, {"id", "username"}, "account")
    account_id = value.get("id")
    username = value.get("username")
    if account_id is not None:
        account_id = text(account_id, "account ID", 100)
    if username is not None:
        require(
            isinstance(username, str)
            and re.fullmatch(r"[A-Za-z0-9._]{1,30}", username),
            "username must be an Instagram handle without @",
        )
        require(username not in {".", ".."}, "a dot-segment is not an account handle")
        username = username.lower()
    require(
        account_id is not None or username is not None,
        "account needs an ID or username",
    )
    key = "id:" + account_id if account_id is not None else "handle:" + username.lower()
    return key, {"id": account_id, "username": username}


def normalize(bundle):
    """Validate observations, deduplicate IDs and conservatively reconcile coverage."""
    fields(
        bundle,
        {"schema_version", "title", "question", "captures", "comment_themes"},
        "bundle",
    )
    require(
        type(bundle.get("schema_version")) is int and bundle["schema_version"] == 1,
        "bundle schema_version must be 1",
    )
    title = text(bundle.get("title", "Creator analysis"), "title", 160)
    question = text(
        bundle.get("question", "Compare the observed participation."), "question", 1000
    )
    captures = bundle.get("captures")
    require(
        isinstance(captures, list) and bool(captures),
        "captures must be a nonempty array",
    )
    normalized, warnings, keys, sources, topics = [], [], set(), set(), {}
    for index, raw in enumerate(captures):
        fields(raw, CAPTURE_FIELDS, f"capture {index + 1}")
        key = text(raw.get("key"), "capture key", 80)
        require(key not in keys, "capture keys must be unique")
        keys.add(key)
        kind = raw.get("kind")
        require(isinstance(kind, str) and kind in KINDS, "unsupported capture kind")
        url = source_url(raw.get("source_url"), kind)
        require(
            (kind, url) not in sources,
            "select one capture per source and kind for a comparison",
        )
        sources.add((kind, url))
        captured = timestamp(raw.get("captured_at_utc"))
        coverage = raw.get("coverage", "unknown")
        require(
            isinstance(coverage, str) and coverage in COVERAGE,
            "invalid coverage status",
        )
        total = count(raw.get("displayed_total"), "displayed_total")
        returned = count(raw.get("returned_total"), "returned_total")
        pages = count(raw.get("pages_read"), "pages_read")
        members = raw.get("members", [])
        require(isinstance(members, list), "members must be an array")
        actors = {}

        def add_actor(value):
            member_key, member = actor(value)
            previous = actors.get(member_key)
            require(
                previous is None
                or not previous["username"]
                or not member["username"]
                or previous["username"] == member["username"],
                "one capture has conflicting labels for an account ID; normalize the label or omit an ambiguous username",
            )
            if previous is None or member["username"]:
                actors[member_key] = member
            return member_key

        for member in members:
            add_actor(member)
        comments = raw.get("comments", [])
        require(isinstance(comments, list), "comments must be an array")
        require(
            kind == "commenters" or not comments,
            "comment records require a commenters capture",
        )
        seen_comments, unidentified = {}, 0
        scope = None
        if kind == "commenters":
            scope = raw.get("comment_scope")
            require(
                isinstance(scope, str)
                and scope in {"top_level", "top_level_and_replies", "visible_subset"},
                "commenters require an explicit comment_scope",
            )
            # Instagram's comment counter counts records, not unique authors.
            require(
                total is None and returned is None,
                "commenters totals must be null; use displayed_comment_total for the comment counter",
            )
            for comment in comments:
                fields(comment, {"id", "author", "is_reply"}, "comment record")
                member_key = add_actor(comment.get("author"))
                reply = comment.get("is_reply", False)
                require(type(reply) is bool, "is_reply must be a boolean")
                require(
                    scope != "top_level" or not reply,
                    "top_level scope cannot contain reply records",
                )
                comment_id = comment.get("id")
                if comment_id is None:
                    unidentified += 1
                else:
                    comment_id = text(comment_id, "comment ID", 100)
                    previous = seen_comments.get(comment_id)
                    require(
                        previous is None or previous == (member_key, reply),
                        "one comment ID has conflicting author or reply observations",
                    )
                    seen_comments[comment_id] = (member_key, reply)
        comment_total = count(
            raw.get("displayed_comment_total"), "displayed_comment_total"
        )
        require(
            kind == "commenters" or comment_total is None,
            "displayed_comment_total requires commenters",
        )
        topic = None
        if kind in {"likers", "commenters"}:
            topic = text(raw.get("topic", "Unlabelled"), "topic", 100)
            require(
                url not in topics or topics[url] == topic,
                "one post has conflicting topic labels",
            )
            topics[url] = topic
        end = text(raw.get("end_evidence", "not_observed"), "end_evidence", 300)
        stop = text(raw.get("stop_reason", "not_recorded"), "stop_reason", 300)
        known = sum(value["id"] is not None for value in actors.values())
        known_handles = {
            value["username"].lower()
            for value in actors.values()
            if value["id"] is not None and value["username"] is not None
        }
        require(
            not any(
                value["id"] is None and value["username"].lower() in known_handles
                for value in actors.values()
            ),
            "one capture mixes ID and handle-only rows for the same handle; normalize ambiguous rows first",
        )
        credible = returned if returned is not None else total
        if total is not None and returned is not None and total != returned:
            coverage = "partial"
            warnings.append(f"{key}: displayed and returned account totals disagree.")
        if credible is not None and len(actors) != credible:
            coverage = "partial"
            warnings.append(
                f"{key}: observed account count does not match the source total."
            )
        if coverage == "end_and_count_match":
            if (
                credible is None
                or known != len(actors)
                or end in {"not_observed", "unknown", "none"}
                or stop != "normal_end"
            ):
                coverage = "partial"
                warnings.append(
                    f"{key}: count/end evidence does not support complete coverage."
                )
        if coverage == "count_match_no_end_signal" and (
            credible is None or known != len(actors)
        ):
            coverage = "partial"
            warnings.append(
                f"{key}: count-match status needs a credible total and stable IDs."
            )
        if coverage == "observed_end_no_total":
            if known != len(actors) or stop != "normal_end" or credible is not None:
                coverage = "partial"
                warnings.append(
                    f"{key}: end-without-total status needs stable IDs, no total and a normal stop."
                )
            elif end in {"not_observed", "unknown", "none"}:
                coverage = "unknown"
                warnings.append(f"{key}: an observed end needs end evidence.")
        if kind == "commenters" and scope == "visible_subset":
            coverage = "partial"
        if kind == "commenters" and comment_total is not None and "comments" in raw:
            if len(seen_comments) > comment_total or (
                scope == "top_level_and_replies"
                and len(seen_comments) + unidentified != comment_total
            ):
                coverage = "partial"
                warnings.append(
                    f"{key}: observed comment records and the displayed comment counter disagree."
                )
        if unidentified:
            warnings.append(
                f"{key}: comment rows without IDs may include repeated observations."
            )
        if known != len(actors):
            warnings.append(f"{key}: handle-only observations are provisional.")
        normalized.append(
            {
                "key": key,
                "kind": kind,
                "source_url": url,
                "captured_at_utc": captured,
                "coverage": coverage,
                "displayed_total": total,
                "returned_total": returned,
                "pages_read": pages,
                "end_evidence": end,
                "stop_reason": stop,
                "topic": topic,
                "comment_scope": scope,
                "displayed_comment_total": comment_total,
                "identified_comment_count": len(seen_comments)
                if "comments" in raw
                else None,
                "unidentified_comment_rows": unidentified
                if "comments" in raw
                else None,
                "observed_accounts": len(actors),
                "known_id_accounts": known,
                "handle_only_accounts": len(actors) - known,
                "actors": actors,
            }
        )
    times = [
        datetime.fromisoformat(c["captured_at_utc"].replace("Z", "+00:00"))
        for c in normalized
    ]
    if (max(times) - min(times)).total_seconds() > 86400:
        warnings.append(
            "Captures span more than 24 hours; they are not a simultaneous audience snapshot."
        )
    if any(c["coverage"] != "end_and_count_match" for c in normalized):
        warnings.append(
            "Some captures lack verified complete coverage. Counts describe observed sets, not complete audiences or evidence of absence."
        )
    themes = bundle.get("comment_themes", [])
    require(isinstance(themes, list), "comment_themes must be an array")
    valid_themes = []
    commenters = {c["key"]: c for c in normalized if c["kind"] == "commenters"}
    for theme in themes:
        fields(theme, {"label", "observed_count", "source_keys"}, "comment theme")
        label = text(theme.get("label"), "theme label", 180)
        number = count(theme.get("observed_count"), "theme observed_count")
        references = theme.get("source_keys")
        require(
            number is not None
            and isinstance(references, list)
            and bool(references)
            and all(isinstance(k, str) and k in commenters for k in references),
            "theme needs a count and valid commenter source_keys",
        )
        require(
            len(set(references)) == len(references), "theme source_keys must be unique"
        )
        bound = sum(
            (commenters[k]["identified_comment_count"] or 0)
            + (commenters[k]["unidentified_comment_rows"] or 0)
            for k in references
        )
        require(number <= bound, "theme count exceeds observed comment records")
        valid_themes.append(
            {"label": label, "observed_count": number, "source_keys": references}
        )
    return title, question, normalized, warnings, valid_themes


def overlap(left, right):
    """Keep ID intersections separate from possible handle matches."""
    certain = {key for key in left.keys() & right.keys() if key.startswith("id:")}
    left_handles, right_handles = defaultdict(set), defaultdict(set)
    for members, handles in [(left, left_handles), (right, right_handles)]:
        for key, account in members.items():
            if account["username"]:
                handles[account["username"].lower()].add(key)
    provisional = set()
    for handle in left_handles.keys() & right_handles.keys():
        a, b = left_handles[handle], right_handles[handle]
        if len(a) == len(b) == 1 and (
            next(iter(a)).startswith("handle:") or next(iter(b)).startswith("handle:")
        ):
            provisional.add(handle)
    return certain, provisional


def analyze(bundle, identity_mode="aggregate"):
    """Return an export-safe model; aggregate output contains no participant IDs/handles."""
    require(
        identity_mode in {"aggregate", "pseudonymous", "identified"},
        "invalid identity mode",
    )
    title, question, captures, warnings, themes = normalize(bundle)
    all_actors = {}
    for capture in sorted(captures, key=lambda c: c["captured_at_utc"]):
        all_actors.update(capture["actors"])
    ordered = sorted(all_actors)
    secrets.SystemRandom().shuffle(ordered)
    aliases = {
        key: f"{'Account' if key.startswith('id:') else 'Handle'} {index + 1:03d}"
        for index, key in enumerate(ordered)
    }

    def labels(keys):
        if identity_mode == "aggregate":
            return []
        return sorted(
            aliases[key]
            if identity_mode == "pseudonymous"
            else (
                (
                    "@"
                    + all_actors[key]["username"]
                    + (" (handle-only)" if all_actors[key]["id"] is None else "")
                )
                if all_actors[key]["username"]
                else "ID " + all_actors[key]["id"]
            )
            for key in keys
        )

    def comparison(a, b):
        certain, possible = overlap(a, b)
        return {
            "known_count": len(certain),
            "possible_handle_count": len(possible),
            "accounts": labels(certain),
            "possible_handles": sorted(possible)
            if identity_mode == "identified"
            else [],
        }

    posts = {}
    audiences = [c for c in captures if c["kind"] in {"followers", "following"}]
    for capture in captures:
        if capture["kind"] in {"likers", "commenters"}:
            posts.setdefault(capture["source_url"], []).append(capture)
    rows, topic_posts = [], defaultdict(list)
    for url, sources in sorted(posts.items()):
        kinds = {c["kind"]: c for c in sources}
        likes, comments = kinds.get("likers"), kinds.get("commenters")
        a = likes["actors"] if likes else {}
        b = comments["actors"] if comments else {}
        participants = dict(a)
        participants.update(b)
        known = {key for key in participants if key.startswith("id:")}
        source_meta = [{k: v for k, v in c.items() if k != "actors"} for c in sources]
        row = {
            "source_url": url,
            "topic": sources[0]["topic"],
            "captured_at_utc": max(c["captured_at_utc"] for c in sources),
            "coverage": "limited_evidence"
            if any(c["coverage"] != "end_and_count_match" for c in sources)
            else "complete_evidence",
            "likers": len(a) if likes else None,
            "commenters": len(b) if comments else None,
            "both": comparison(a, b) if likes and comments else None,
            "like_not_observed_comment": len(
                {k for k in a if k.startswith("id:")} - set(b)
            )
            if likes and comments
            else None,
            "comment_not_observed_like": len(
                {k for k in b if k.startswith("id:")} - set(a)
            )
            if likes and comments
            else None,
            "known_accounts": len(known),
            "handle_only_accounts": len(participants) - len(known),
            "accounts": labels(participants),
            "sources": source_meta,
            "audiences": [
                {
                    "source_key": c["key"],
                    "source_url": c["source_url"],
                    "kind": c["kind"],
                    "overlap": comparison(participants, c["actors"]),
                }
                for c in audiences
            ],
        }
        rows.append(row)
        topic_posts[row["topic"]].append((url, participants))
    require(bool(rows), "creator analysis needs at least one post/Reel capture")
    topic_rows, topic_members = [], {}
    for topic, members_by_post in sorted(topic_posts.items()):
        union, frequency = {}, Counter()
        handle_posts, handle_ids, fallback_handles = (
            defaultdict(set),
            defaultdict(set),
            set(),
        )
        for post_url, members in members_by_post:
            union.update(members)
            frequency.update(k for k in members if k.startswith("id:"))
            for member in members.values():
                handle = member["username"]
                if handle:
                    handle_posts[handle].add(post_url)
                    if member["id"] is None:
                        fallback_handles.add(handle)
                    else:
                        handle_ids[handle].add(member["id"])
        known = {key for key in union if key.startswith("id:")}
        topic_members[topic] = union
        topic_rows.append(
            {
                "topic": topic,
                "posts": len(members_by_post),
                "known_accounts": len(known),
                "handle_only_accounts": len(union) - len(known),
                "repeat_known_accounts": sum(n >= 2 for n in frequency.values()),
                "possible_repeat_handles": sum(
                    len(handle_posts[h]) >= 2 and len(handle_ids[h]) <= 1
                    for h in fallback_handles
                ),
            }
        )
    for row in topic_rows:
        others = set().union(
            *(set(v) for k, v in topic_members.items() if k != row["topic"])
        )
        row["only_observed_in_topic"] = len(
            {k for k in topic_members[row["topic"]] if k.startswith("id:")} - others
        )
    topic_overlap = []
    names = sorted(topic_members)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            topic_overlap.append(
                {
                    "first": first,
                    "second": second,
                    **comparison(topic_members[first], topic_members[second]),
                }
            )
    post_likers_by_url = {
        url: (sources.get("likers")["actors"] if "likers" in sources else {})
        for url, sources in ((u, {c["kind"]: c for c in s}) for u, s in posts.items())
    }
    post_commenters_by_url = {
        url: (sources.get("commenters")["actors"] if "commenters" in sources else {})
        for url, sources in ((u, {c["kind"]: c for c in s}) for u, s in posts.items())
    }
    engager_stats = defaultdict(
        lambda: {"liked": 0, "commented": 0, "both": 0, "posts": 0}
    )
    for url in posts:
        likers_set = set(post_likers_by_url[url])
        commenters_set = set(post_commenters_by_url[url])
        for k in likers_set | commenters_set:
            is_like = k in likers_set
            is_comment = k in commenters_set
            engager_stats[k]["posts"] += 1
            if is_like:
                engager_stats[k]["liked"] += 1
            if is_comment:
                engager_stats[k]["commented"] += 1
            if is_like and is_comment:
                engager_stats[k]["both"] += 1

    multi_post_count = sum(
        s["posts"] >= 2 for k, s in engager_stats.items() if k.startswith("id:")
    )
    repeat_both_count = sum(
        s["both"] >= 2 for k, s in engager_stats.items() if k.startswith("id:")
    )
    all_known_count = sum(k.startswith("id:") for k in engager_stats)

    loyalty = {
        "multi_post_accounts": multi_post_count,
        "multi_post_both_accounts": repeat_both_count,
        "total_active_accounts": all_known_count,
        "engagers": [],
    }
    if identity_mode != "aggregate":
        ranked = sorted(
            [k for k in engager_stats if engager_stats[k]["posts"] >= 2],
            key=lambda k: (
                engager_stats[k]["both"],
                engager_stats[k]["posts"],
                engager_stats[k]["commented"],
                engager_stats[k]["liked"],
            ),
            reverse=True,
        )
        loyalty["engagers"] = [
            {
                "label": labels([k])[0],
                "posts": engager_stats[k]["posts"],
                "liked": engager_stats[k]["liked"],
                "commented": engager_stats[k]["commented"],
                "both": engager_stats[k]["both"],
            }
            for k in ranked
        ]
    return {
        "schema_version": 1,
        "title": title,
        "question": question,
        "identity_mode": identity_mode,
        "generated_at_utc": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "warnings": list(dict.fromkeys(warnings)),
        "posts": rows,
        "topics": topic_rows,
        "topic_overlap": topic_overlap,
        "loyalty": loyalty,
        "comment_themes": themes,
        "sources": [{k: v for k, v in c.items() if k != "actors"} for c in captures],
    }


def render_report(model, language="en"):
    """Embed only the already-sanitized export model, with no network resources."""
    require(language in {"en", "tr"}, "report language must be en or tr")
    template = Path(__file__).resolve().parent.parent / "assets" / "creator-report.html"
    payload = (
        json.dumps(model, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    replacements = {
        "__NONCE__": secrets.token_urlsafe(24),
        "__LANG__": language,
        "__TITLE__": html.escape(model["title"], quote=True),
        "__REPORT_DATA__": payload,
    }
    return re.sub(
        r"__NONCE__|__LANG__|__TITLE__|__REPORT_DATA__",
        lambda match: replacements[match.group()],
        template.read_text(encoding="utf-8"),
    )


def write_new(path, content):
    """Create a private output without overwriting a previous capture/report."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="normalized JSON path, or - for stdin"
    )
    parser.add_argument("--html", help="create a requested self-contained report")
    parser.add_argument("--json", help="create a requested export-safe JSON model")
    parser.add_argument(
        "--identity-mode",
        choices=["aggregate", "pseudonymous", "identified"],
        default="aggregate",
    )
    parser.add_argument("--language", choices=["en", "tr"], default="en")
    args = parser.parse_args()
    try:
        raw = (
            sys.stdin.read()
            if args.input == "-"
            else Path(args.input).expanduser().read_text(encoding="utf-8")
        )
        model = analyze(json.loads(raw), args.identity_mode)
        outputs = [Path(p).expanduser().resolve() for p in [args.html, args.json] if p]
        require(
            len(outputs) == len(set(outputs)),
            "HTML and JSON need different output paths",
        )
        require(
            not any(p.exists() for p in outputs),
            "an output path already exists; choose a new timestamped name",
        )
        if args.html:
            write_new(args.html, render_report(model, args.language))
        if args.json:
            write_new(args.json, json.dumps(model, ensure_ascii=False, indent=2) + "\n")
        if not args.html and not args.json:
            print(json.dumps(model, ensure_ascii=False, indent=2))
    except (InputError, OSError, json.JSONDecodeError) as exc:
        # Never echo raw input or unknown field names (which may contain session material).
        print(f"Analysis could not be completed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
