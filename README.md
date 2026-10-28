# Instagram List Inspector

An open-source **Codex and Claude skill** for comparing Instagram lists accessible in your signed-in browser. It runs on demand and reports observed data and coverage limits.

The skill can compare followers and following across accounts, find mutuals and non-follow-backs, intersect post/Reels likers with account audiences, spot repeat likers across posts, compare dated captures, and analyze commenters alongside post likers and user-labelled content topics. It joins accounts by platform ID where available and tells you when a list is incomplete. Results appear in chat by default; local JSON, CSV, or HTML reports are optional.

## Requirements

- Codex or Claude with an available signed-in browser/computer tool. Codex uses CDP only when the tool explicitly supports it; Claude defaults to visible UI observation.
- For Claude Code, see [Chrome integration](https://code.claude.com/docs/en/chrome): launch with `claude --chrome` and check `/chrome`. Installing this skill does not activate browser tools.
- An Instagram account with legitimate access to the specific lists you ask to inspect.
- Your own judgment about applicable Instagram terms, privacy rules, and permissions. No password, session-cookie copy, ZIP export, or CLI setup is required by the skill.

## Install and use

Clone this repository into your personal Codex skills directory so that `SKILL.md` is inside the `instagram-list-inspector` folder:

```bash
git clone https://github.com/GreedyC/instagram-list-inspector.git "$HOME/.codex/skills/instagram-list-inspector"
```

For Claude Code, clone into `~/.claude/skills/instagram-list-inspector` instead. The shared entrypoint routes separately for each client. Restart or refresh skill discovery if needed, then ask for a specific comparison, for example:

> `$instagram-list-inspector` Compare the accounts followed by @account_a and @account_b. Show the shared handles and tell me whether both lists were complete.

The browser may request login, verification, or CDP approval. Complete those prompts yourself. The skill does not ask you to reveal credentials. If browser/CDP access is unavailable, it reports the limitation instead of claiming a complete result.

## Privacy and limitations

- The workflow observes visible Instagram UI by default. Unofficial web requests are an optional route only when the current browser tool explicitly permits it; either route can change or stop working. It does not claim Meta/Instagram affiliation or approval.
- Meta says automated data collection without permission can violate its terms. Use only where you have appropriate rights and permission; respect platform limits and stop on challenges or rate limits. See [Meta's scraping guidance](https://www.facebook.com/help/463983701520800) and the [Instagram Terms of Use](https://help.instagram.com/581066165581870).
- Private or unavailable lists are not bypassed. Missing results from partial captures are **not** proof that a person did not follow or like something.
- Instagram may end pagination before the observed identity-key count (IDs, or normalized handles when IDs are unavailable) matches a profile total. The skill makes at most one bounded consistency pass and preserves each pass's evidence separately. Handle-only identity stays provisional even when counts match; unresolved mismatches remain partial.
- Session headers stay in browser memory during a run. Never publish cookies, raw responses, screenshots containing private information, or generated reports. The repository contains skill instructions, a local analysis helper and synthetic fixtures, not real account data.
- Historical comparisons require an earlier user-requested local snapshot. The skill does not start background monitoring.

This project is licensed under MIT; that license does not grant rights to Instagram data or waive platform terms.

## Türkçe kısa rehber

Bu proje, Codex içinde çalışan bir **skill**: erişebildiğin Instagram takipçi/takip edilen ve gönderi-Reels beğenen listelerini karşılaştırır. Ortak hesapları, karşılıklı takibi, geri takip etmeyenleri ve tarihli kayıtlar arasındaki değişimleri gösterebilir. Eksik veri varsa bunu açıkça söyler; “listede görünmedi” sonucunu “kesinlikle yok” diye sunmaz.

Kurulum için yukarıdaki `git clone` komutunu kullan. Ardından örneğin şunu yaz:

> `$instagram-list-inspector` @hesap_a ile @hesap_b'nin ortak takip ettiklerini bul; iki listenin de kapsamını belirt.

Şifre, çerez, ZIP veya elle liste yapıştırman gerekmez. Codex veya Claude içinde kullanılabilir tarayıcı/computer-use aracı gerekir; CDP zorunlu değildir. Bu, resmi Instagram API'si değildir; platform kurallarını ve kişilerin gizliliğini gözeterek kullan.


## Creator analysis and clickable reports

Ask the agent to compare posts by topic (for example, Coffee vs Coding), cross
observed commenters with post likers/followers, or summarize questions in comments
it can actually observe. The agent uses its available browser/computer tools; a
separate agent, collector service or user-run CLI is not required.

A Python 3.10+ standard-library helper supplies repeatable ID-based calculations
and requested self-contained HTML reports. The report has post search, topic and
capture-date filters, sorting and inline source evidence; it runs offline. Whole-
report topic counts remain separate from post-table filters. Participant identities
in membership lists are omitted from aggregate exports; requested source URLs and descriptive metadata remain. The agent must keep descriptive fields neutral for sharing. Reports support optional report-local pseudonyms or
explicitly requested identified reports. No third-party Python packages are needed.

See [creator-analysis.md](references/creator-analysis.md) for the normalized input,
comment-scope rules and agent workflow. New features are verified with synthetic
fixtures; that is not a claim that Instagram currently exposes every requested
list or that live multi-account collection has been validated.
