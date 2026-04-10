"""
K-pop Intelligence Newsletter Generator
매일 GitHub Actions에서 자동 실행됩니다.

필요한 환경변수 (GitHub Secrets에 설정):
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  YOUTUBE_API_KEY
"""

import os
import datetime
import requests
from pathlib import Path


# ────────────────────────────────────────────
# 0. 설정
# ────────────────────────────────────────────

TODAY  = datetime.date.today().isoformat()
DAY_KO = ["월", "화", "수", "목", "금", "토", "일"][datetime.date.today().weekday()]
OUTPUT_DIR = Path("newsletters")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 팔로우할 아티스트 (Spotify Artist ID) ──
# Artist ID 찾는 법: Spotify에서 아티스트 페이지 → 공유 → 링크 복사
# https://open.spotify.com/artist/[여기가 ID]
ARTISTS = {
    "aespa":       "2cnMpRsRX83sFl96xKXQ1",
    "SEVENTEEN":   "7nqOGox5dQiUgmxGUCjkjh",
    "ILLIT":       "3GjN0Vc5AkRBGAMuRXhaDI",
    "NewJeans":    "2NZVRjbzIDfuSE6ESWJvvU",
    "BINI":        "6MdRFpKXAMbBr88b1T3UM7",
    "NMIXX":       "1tmxpdDbyKoCOXlSb7MGFU",
    "LE SSERAFIM": "6HvZYsbFfjnjFrWF950C9d",
    # 아티스트 추가하려면 여기에 계속 붙여넣으세요
    # "아티스트명": "Spotify Artist ID",
}

# ── MV 조회수 트래킹 (YouTube Video ID) ──
# Video ID 찾는 법: 유튜브 MV 주소 → ?v= 뒤의 값
# https://www.youtube.com/watch?v=[여기가 ID]
MV_TRACKING = [
    {"artist": "BLACKPINK", "title": "DDU-DU DDU-DU", "video_id": "IHNzOHi8sJs"},
    {"artist": "BTS",       "title": "Dynamite",       "video_id": "gdZLi9oWNZg"},
    {"artist": "ILLIT",     "title": "Magnetic",       "video_id": "JNTnhBmERQk"},
    {"artist": "SEVENTEEN", "title": "MAESTRO",        "video_id": "tZj8ov1K7Zs"},
    {"artist": "aespa",     "title": "Whiplash",       "video_id": "wq7JCJpGSe0"},
    # MV 추가하려면 여기에 계속 붙여넣으세요
    # {"artist": "아티스트명", "title": "곡제목", "video_id": "유튜브ID"},
]

# ── 외신 RSS 피드 ──
RSS_SOURCES = [
    {"name": "Billboard",          "url": "https://www.billboard.com/feed/"},
    {"name": "Rolling Stone",      "url": "https://www.rollingstone.com/feed/"},
    {"name": "Pitchfork",          "url": "https://pitchfork.com/rss/news/"},
    {"name": "NME",                "url": "https://www.nme.com/feed/"},
    {"name": "The Guardian Music", "url": "https://www.theguardian.com/music/rss"},
    {"name": "Variety",            "url": "https://variety.com/feed/"},
]

RSS_KEYWORDS = [
    "k-pop", "kpop", "k pop",
    "aespa", "bts", "blackpink", "seventeen", "newjeans",
    "illit", "bini", "nmixx", "le sserafim", "stray kids", "ive", "twice",
]


# ────────────────────────────────────────────
# 1. Spotify: 신보 감지
# ────────────────────────────────────────────

def get_spotify_token() -> str:
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_new_releases(token: str, days: int = 30) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    cutoff  = datetime.date.today() - datetime.timedelta(days=days)
    releases = []

    for artist_name, artist_id in ARTISTS.items():
        try:
            r = requests.get(
                f"https://api.spotify.com/v1/artists/{artist_id}/albums",
                headers=headers,
                params={"album_type": "album,single,ep", "limit": 5, "market": "KR"},
                timeout=10,
            )
            for album in r.json().get("items", []):
                raw_date = album.get("release_date", "")
                try:
                    rel_date = datetime.date.fromisoformat(raw_date[:10])
                except ValueError:
                    continue
                if rel_date >= cutoff:
                    releases.append({
                        "artist":       artist_name,
                        "title":        album["name"],
                        "type":         album["album_type"],
                        "release_date": raw_date[:10],
                        "spotify_url":  album["external_urls"]["spotify"],
                    })
        except Exception as e:
            print(f"  Spotify error ({artist_name}): {e}")

    releases.sort(key=lambda x: x["release_date"], reverse=True)

    # 중복 제거
    seen, unique = set(), []
    for r in releases:
        key = (r["artist"], r["title"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ────────────────────────────────────────────
# 2. YouTube: MV 조회수
# ────────────────────────────────────────────

def fetch_mv_views() -> list[dict]:
    api_key   = os.environ["YOUTUBE_API_KEY"]
    video_ids = ",".join(mv["video_id"] for mv in MV_TRACKING)
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": video_ids, "key": api_key},
            timeout=10,
        )
        stats = {item["id"]: item["statistics"] for item in r.json().get("items", [])}
    except Exception as e:
        print(f"  YouTube error: {e}")
        stats = {}

    results = []
    for mv in MV_TRACKING:
        count = int(stats.get(mv["video_id"], {}).get("viewCount", 0))
        results.append({**mv, "views": count})

    results.sort(key=lambda x: x["views"], reverse=True)
    return results


def fmt_views(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    return f"{n:,}"


# ────────────────────────────────────────────
# 3. RSS: 외신 헤드라인 수집 (원문 제목 + 링크만)
# ────────────────────────────────────────────

def fetch_rss_articles(max_per_source: int = 3) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        print("  feedparser 없음. pip install feedparser 실행하세요.")
        return []

    articles = []
    for src in RSS_SOURCES:
        try:
            feed  = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_source:
                    break
                combined = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                if any(kw in combined for kw in RSS_KEYWORDS):
                    articles.append({
                        "source": src["name"],
                        "title":  entry.get("title", "").strip(),
                        "url":    entry.get("link", ""),
                        "date":   entry.get("published", "")[:16],
                    })
                    count += 1
        except Exception as e:
            print(f"  RSS error ({src['name']}): {e}")

    return articles


# ────────────────────────────────────────────
# 4. 인트로 텍스트 (API 없이 자동 생성)
# ────────────────────────────────────────────

def build_intro(releases: list[dict], articles: list[dict]) -> str:
    parts = []
    if releases:
        names = ", ".join(f"{r['artist']} 《{r['title']}》" for r in releases[:3])
        suffix = f" 외 {len(releases)-3}건" if len(releases) > 3 else ""
        parts.append(f"이번 주 주목할 신보: {names}{suffix}.")
    if articles:
        parts.append(f"외신에서는 총 {len(articles)}건의 K-pop 관련 기사가 수집됐습니다.")
    if not parts:
        parts.append("오늘은 새로운 신보 소식이 없습니다.")
    parts.append("아래에서 신보 발매·MV 조회수·외신 헤드라인을 확인하세요.")
    return " ".join(parts)


# ────────────────────────────────────────────
# 5. HTML 렌더링
# ────────────────────────────────────────────

def build_release_cards(releases: list[dict]) -> str:
    if not releases:
        return "<p style='color:#9C9B96;font-size:13px;padding:1rem 0;'>최근 30일 내 신보 없음</p>"

    type_map = {"album": "정규앨범", "single": "싱글", "ep": "EP", "compilation": "컴필레이션"}
    tag_map  = {"album": "tag-purple", "single": "tag-teal", "ep": "tag-blue", "compilation": "tag-amber"}

    cards = []
    for r in releases:
        type_label = type_map.get(r["type"], r["type"].upper())
        tag_cls    = tag_map.get(r["type"], "tag-pink")
        cards.append(f"""
  <div class="card">
    <div class="card-row">
      <div class="card-icon">🎵</div>
      <div class="card-body">
        <div class="card-title">{r['artist']} — 《{r['title']}》</div>
        <div class="card-source">발매일 {r['release_date']} · {type_label}</div>
        <div class="tags" style="margin-top:8px;">
          <span class="tag {tag_cls}">{type_label}</span>
          <a href="{r['spotify_url']}" target="_blank"
             style="font-size:11px;font-weight:500;color:#0D6B52;text-decoration:none;
                    padding:2px 9px;background:#E3F7F1;border-radius:99px;">
            Spotify →
          </a>
        </div>
      </div>
    </div>
  </div>""")
    return "\n".join(cards)


def build_mv_rows(mv_data: list[dict]) -> str:
    if not mv_data:
        return "<p style='color:#9C9B96;font-size:13px;'>조회수 데이터 없음</p>"
    max_views = mv_data[0]["views"] or 1
    colors    = ["#D4537E", "#378ADD", "#EF9F27", "#1D9E75", "#7F77DD"]
    rows = []
    for i, mv in enumerate(mv_data):
        pct   = int(mv["views"] / max_views * 100)
        color = colors[i % len(colors)]
        rows.append(f"""
  <div class="mv-row">
    <div class="mv-rank">{i+1}</div>
    <div class="mv-name">{mv['artist']} — {mv['title']}</div>
    <div class="mv-track"><div class="mv-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="mv-val">{fmt_views(mv['views'])}</div>
  </div>""")
    return "\n".join(rows)


def build_article_cards(articles: list[dict]) -> str:
    if not articles:
        return "<p style='color:#9C9B96;font-size:13px;'>오늘 수집된 외신 기사 없음</p>"
    cards = []
    for a in articles:
        date_str = f" · {a['date']}" if a["date"] else ""
        cards.append(f"""
  <div class="article-card">
    <div class="article-source">{a['source']}{date_str}</div>
    <a class="article-title" href="{a['url']}" target="_blank">{a['title']}</a>
  </div>""")
    return "\n".join(cards)


def render_html(releases, mv_data, articles) -> str:
    intro         = build_intro(releases, articles)
    release_cards = build_release_cards(releases)
    mv_rows       = build_mv_rows(mv_data)
    article_cards = build_article_cards(articles)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>K-pop Intelligence · {TODAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  :root {{
    --bg:#F7F5F0; --surface:#FFF;
    --border:rgba(0,0,0,.08); --border-strong:rgba(0,0,0,.14);
    --text-primary:#111110; --text-secondary:#5C5B57; --text-muted:#9C9B96;
    --accent:#1A1A18;
    --purple:#4A3FB5; --purple-bg:#EEEDFC;
    --blue:#1558A8;   --blue-bg:#E8F0FA;
    --pink:#9A2E5E;   --pink-bg:#FAEAF2;
    --teal:#0D6B52;   --teal-bg:#E3F7F1;
    --amber:#7A4B08;  --amber-bg:#FDF0D8;
  }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text-primary); font-size:15px; line-height:1.7; }}
  .page {{ max-width:680px; margin:0 auto; padding:0 1.25rem 4rem; }}
  .header {{ padding:2.5rem 0 2rem; border-bottom:1px solid var(--border-strong); margin-bottom:2rem; }}
  .logo-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:1.25rem; }}
  .logo {{ font-family:'DM Serif Display',serif; font-size:13px; letter-spacing:.18em; text-transform:uppercase; color:var(--text-muted); }}
  .date-badge {{ font-size:11px; font-weight:500; padding:3px 10px; background:var(--accent); color:#FFF; border-radius:99px; }}
  .header h1 {{ font-family:'DM Serif Display',serif; font-size:34px; font-weight:400; line-height:1.2; margin-bottom:.5rem; }}
  .header h1 em {{ font-style:italic; color:var(--text-secondary); }}
  .header-sub {{ font-size:13px; color:var(--text-muted); }}
  .intro {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.25rem 1.5rem; margin-bottom:2.5rem; font-size:14px; color:var(--text-secondary); line-height:1.75; }}
  .section {{ margin-bottom:2.5rem; }}
  .section-label {{ font-size:10px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; color:var(--text-muted); padding-bottom:.75rem; border-bottom:1px solid var(--border); margin-bottom:1rem; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; margin-bottom:.6rem; }}
  .card-row {{ display:flex; gap:14px; align-items:flex-start; }}
  .card-icon {{ width:52px; height:52px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0; border:1px solid var(--border); }}
  .card-body {{ flex:1; min-width:0; }}
  .card-title {{ font-size:14px; font-weight:500; margin-bottom:3px; }}
  .card-source {{ font-size:11px; color:var(--text-muted); }}
  .tags {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .tag {{ font-size:11px; font-weight:500; padding:2px 9px; border-radius:99px; }}
  .tag-purple {{ background:var(--purple-bg); color:var(--purple); }}
  .tag-blue   {{ background:var(--blue-bg);   color:var(--blue); }}
  .tag-pink   {{ background:var(--pink-bg);   color:var(--pink); }}
  .tag-teal   {{ background:var(--teal-bg);   color:var(--teal); }}
  .tag-amber  {{ background:var(--amber-bg);  color:var(--amber); }}
  .mv-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .mv-row {{ display:flex; align-items:center; gap:12px; margin-bottom:10px; }}
  .mv-row:last-of-type {{ margin-bottom:0; }}
  .mv-rank {{ font-size:11px; font-weight:500; color:var(--text-muted); min-width:16px; text-align:right; }}
  .mv-name {{ font-size:13px; color:var(--text-secondary); min-width:130px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .mv-track {{ flex:1; height:5px; background:var(--bg); border-radius:99px; overflow:hidden; }}
  .mv-fill {{ height:100%; border-radius:99px; }}
  .mv-val {{ font-size:12px; font-weight:500; color:var(--text-primary); min-width:40px; text-align:right; }}
  .mv-note {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}
  .article-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1rem 1.25rem; margin-bottom:.6rem; }}
  .article-source {{ font-size:10px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; color:var(--text-muted); margin-bottom:5px; }}
  .article-title {{ font-size:14px; font-weight:500; color:var(--text-primary); text-decoration:none; line-height:1.45; display:block; }}
  .article-title:hover {{ color:var(--purple); }}
  .footer {{ border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; font-size:12px; color:var(--text-muted); display:flex; align-items:center; justify-content:space-between; }}
  .footer a {{ color:var(--text-muted); text-decoration:none; }}
  @media(max-width:540px) {{
    .header h1 {{ font-size:26px; }}
    .mv-name {{ min-width:90px; }}
    .footer {{ flex-direction:column; gap:8px; text-align:center; }}
  }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div class="logo-row">
      <div class="logo">K-pop Intelligence</div>
      <div class="date-badge">{TODAY}</div>
    </div>
    <h1>케이팝 인텔리전스<br><em>데일리 브리핑</em></h1>
    <div class="header-sub">{DAY_KO}요일 · 엔터산업 담당자를 위한 자동 업데이트</div>
  </div>

  <div class="intro">{intro}</div>

  <div class="section">
    <div class="section-label">신보 발매 소식 (최근 30일)</div>
    {release_cards}
  </div>

  <div class="section">
    <div class="section-label">주요 MV 조회수</div>
    <div class="mv-card">
      {mv_rows}
      <div class="mv-note">* 유튜브 기준 누적 조회수 · 매일 오전 8시 자동 업데이트</div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">외신 헤드라인</div>
    {article_cards}
  </div>

  <div class="footer">
    <span>K-pop Intelligence · 매일 자동 업데이트</span>
    <span><a href="../index.html">← 최신호</a> · <a href="../archive.html">아카이브</a></span>
  </div>

</div>
</body>
</html>"""


# ────────────────────────────────────────────
# 6. 메인 실행
# ────────────────────────────────────────────

def main():
    print(f"[{TODAY}] K-pop Intelligence 생성 시작...")

    print("  → Spotify 신보 조회 중...")
    token    = get_spotify_token()
    releases = fetch_new_releases(token, days=30)
    print(f"     {len(releases)}개 신보 발견")

    print("  → YouTube MV 조회수 수집 중...")
    mv_data = fetch_mv_views()

    print("  → 외신 RSS 수집 중...")
    articles = fetch_rss_articles(max_per_source=3)
    print(f"     {len(articles)}개 기사 수집")

    print("  → HTML 렌더링 중...")
    html = render_html(releases, mv_data, articles)

    output_path = OUTPUT_DIR / f"{TODAY}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  → 완료: {output_path}")


if __name__ == "__main__":
    main()
