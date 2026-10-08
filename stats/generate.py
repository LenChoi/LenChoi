#!/usr/bin/env python3
"""GitHub 통계 카드를 만든다 — **비공개 저장소까지 센다**.

github-readme-stats 의 공개 인스턴스는 남의 비공개 저장소를 읽을 권한이 없어
`count_private=true` 를 붙여도 공개 활동만 보여 준다. 그래서 직접 만든다.

쓰는 법:
    gh auth status          # 비공개 저장소를 읽을 수 있는 계정이어야 한다
    python3 stats/generate.py
    git add stats && git commit && git push

숫자는 돌린 시점의 값이다. 갱신하려면 다시 돌린다.
"""
import json
import subprocess
from datetime import date

USER = "LenChoi"


def gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def contributions() -> dict:
    q = """
    { user(login: "%s") { contributionsCollection {
        totalCommitContributions
        restrictedContributionsCount
        contributionCalendar { totalContributions }
    } } }
    """ % USER
    return json.loads(gh(["api", "graphql", "-f", f"query={q}",
                          "--jq", ".data.user.contributionsCollection"]))


def search_count(kind: str) -> int:
    out = gh(["api", "-X", "GET", "search/issues",
              "-f", f"q=author:{USER} type:{kind}", "--jq", ".total_count"])
    return int(out.strip())


def languages() -> list[tuple[str, int, str]]:
    """접근 가능한 저장소 전부의 언어를 바이트로 합산한다. 포크와 보관된 것은 뺀다."""
    q = """
    query($endCursor: String) { viewer { repositories(
        first: 50, after: $endCursor,
        affiliations: [OWNER, ORGANIZATION_MEMBER, COLLABORATOR], isFork: false
    ) {
        pageInfo { hasNextPage endCursor }
        nodes { isArchived languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
            edges { size node { name color } } } }
    } } }
    """
    raw = gh(["api", "graphql", "--paginate", "-f", f"query={q}",
              "--jq", ".data.viewer.repositories.nodes[]"])
    total: dict[str, int] = {}
    colors: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        repo = json.loads(line)
        if repo.get("isArchived"):
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            total[name] = total.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    ranked = sorted(total.items(), key=lambda kv: -kv[1])[:6]
    whole = sum(total.values()) or 1
    return [(name, size / whole * 100, colors[name]) for name, size in ranked]


THEMES = {
    "dark": dict(bg="#0d1117", title="#58a6ff", text="#c9d1d9", dim="#8b949e", track="#21262d"),
    "light": dict(bg="#ffffff", title="#0969da", text="#1f2328", dim="#59636e", track="#eaeef2"),
}

W, H = 840, 232


def card(theme: str, rows: list[tuple[str, str]], langs: list[tuple[str, float, str]]) -> str:
    c = THEMES[theme]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{USER} GitHub stats">',
        f'<rect width="{W}" height="{H}" rx="10" fill="{c["bg"]}"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<text x="26" y="36" fill="{c["title"]}" font-size="17" font-weight="600">'
        f'{USER} — including private work</text>',
    ]
    # 왼쪽: 수치
    y = 76
    for label, value in rows:
        out.append(f'<text x="26" y="{y}" fill="{c["dim"]}" font-size="13.5">{label}</text>')
        out.append(f'<text x="330" y="{y}" fill="{c["text"]}" font-size="13.5" '
                   f'font-weight="700" text-anchor="end">{value}</text>')
        y += 29
    # 오른쪽: 언어 막대
    bx, bw = 390, 424
    out.append(f'<text x="{bx}" y="76" fill="{c["dim"]}" font-size="13.5">Most used languages</text>')
    out.append(f'<rect x="{bx}" y="88" width="{bw}" height="9" rx="4.5" fill="{c["track"]}"/>')
    off = 0.0
    for _, pct, color in langs:
        seg = bw * pct / 100
        out.append(f'<rect x="{bx + off:.1f}" y="88" width="{max(seg, 1):.1f}" height="9" fill="{color}"/>')
        off += seg
    for i, (name, pct, color) in enumerate(langs):
        col, row = i % 2, i // 2
        lx, ly = bx + col * 212, 124 + row * 26
        out.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>')
        out.append(f'<text x="{lx + 18}" y="{ly}" fill="{c["text"]}" font-size="12.5">'
                   f'{name} {pct:.1f}%</text>')
    out.append(f'<text x="26" y="{H - 16}" fill="{c["dim"]}" font-size="11">'
               f'generated {date.today().isoformat()} · private repositories included</text>')
    out.append("</g></svg>")
    return "\n".join(out)


def main() -> None:
    con = contributions()
    commits = con["totalCommitContributions"] + con["restrictedContributionsCount"]
    rows = [
        ("Contributions (last year)", f'{con["contributionCalendar"]["totalContributions"]:,}'),
        ("Commits (last year)", f"{commits:,}"),
        ("Pull requests (all time)", f"{search_count('pr'):,}"),
        ("Issues (all time)", f"{search_count('issue'):,}"),
    ]
    # `totalRepositoriesWithContributedCommits` 는 싣지 않는다. 비공개 저장소를 세지
    # 않아서 커밋이 오천 건인데 저장소가 넷으로 보인다 — 맞는 수치가 아니라 오해다.
    langs = languages()
    for theme in THEMES:
        path = f"stats/github-stats-{theme}.svg"
        with open(path, "w") as f:
            f.write(card(theme, rows, langs))
        print(f"  {path}")
    for label, value in rows:
        print(f"    {label:30} {value}")


if __name__ == "__main__":
    main()
