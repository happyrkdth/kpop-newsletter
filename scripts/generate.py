"""
K-pop Intelligence Newsletter Generator
매일 GitHub Actions에서 자동 실행됩니다.

필요한 환경변수 (GitHub Secrets):
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

# 팔로우할 아티스트 (Spotify Artist ID)
# Artist ID: Spotify에서 아티스트 페이지 → 공유 → 링크의 /artist/ 뒷부분
ARTISTS = {
    "aespa":        "2cnMpRsRX83sFl96xKXQ1",
    "SEVENTEEN":    "7nqOGox5dQiUgmxGUCjkjh",
    "ILLIT":        "3GjN0Vc5AkRBGAMuRXhaDI",
    "NewJeans":     "2NZVRjbzIDfuSE6ESWJvvU",
    "BINI":         "6MdRFpKXAMbBr88b1T3UM7",
    "NMIXX":        "1tmxpdDbyKoCOXlSb7MGFU",
    "LE SSERAFIM":  "6HvZYsbFfjnjFrWF950C9d",
    "IVE":          "6RHTUrRF63xao58xh9FXYJ",
    "TWICE":        "7n2Ycct7Beij7Dj7meI4X0",
    "Stray Kids":   "2b4LTnUMBB34DWnFMKVEDP",
    "EXO":          "3cjEqqElzeQVFFRNBcHISM",
    "NCT 127":      "0h4tLJGFQuCNKqk8zTtGlC",
    "BLACKPINK":    "41MozSoPIsD1dJM0CLPjZF",
    "BTS":          "3Nrfpe0tUJi4K4DXYWgMUX",
    "GOT7":         "3gIRvgZssIb9aiirIg0nI3",
    "ENHYPEN":      "0bktO5A1yBhMVTXXbQEjxW",
    "TXT":          "4vGrte8FDu062Ntj0RsPiZ",
    "ATEEZ":        "1Cd373x7Nf6QEHBHB7DNVG",
    # 아티스트 추가: "이름": "Spotify Artist ID"
}


# ────────────────────────────────────────────
# 1. Spotify 토큰
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


# ────────────────────────────────────────────
# 2. 신보 & 컴백 일정
# ────────────────────────────────────────────

def fetch_releases(token: str) -> tuple[list[dict], list[dict]]:
    """
    최근 30일 발매 → recent (신보 발매 소식)
    향후 60일 예정 → upcoming (컴백 일정)
    """
    headers  = {"Authorization": f"Bearer {token}"}
    today    = datetime.date.today()
    past_30  = today - datetime.timedelta(days=30)
    future_60= today + datetime.timedelta(days=60)

    recent   = []
    upcoming = []
    seen     = set()

    for artist_name, artist_id in ARTISTS.items():
        try:
            r = requests.get(
                f"https://api.spotify.com/v1/artists/{artist_id}/albums",
                headers=headers,
                params={"album_type": "album,single,ep", "limit": 10, "market": "KR"},
                timeout=10,
            )
            for album in r.json().get("items", []):
                raw = album.get("release_date", "")
                try:
                    rel_date = datetime.date.fromisoformat(raw[:10])
                except ValueError:
                    continue

                key = (artist_name, album["name"])
                if key in seen:
                    continue
                seen.add(key)

                item = {
                    "artist":       artist_name,
                    "title":        album["name"],
                    "type":         album["album_type"],
                    "release_date": raw[:10],
                    "spotify_url":  album["external_urls"]["spotify"],
                    "image_url":    album["images"][0]["url"] if album["images"] else "",
                }

                if past_30 <= rel_date <= today:
                    recent.append(item)
                elif today < rel_date <= future_60:
                    upcoming.append(item)

        except Exception as e:
            print(f"  Spotify error ({artist_name}): {e}")

    recent.sort(key=lambda x: x["release_date"], reverse=True)
    upcoming.sort(key=lambda x: x["release_date"])
    return recent, upcoming


# ────────────────────────────────────────────
# 3. YouTube: 최근 컴백 아티스트 MV 조회수
# ────────────────────────────────────────────

def fetch_recent_mv_views(recent_releases: list[dict]) -> list[dict]:
    """최근 발매된 아티스트의 MV를 YouTube에서 검색해서 조회수 가져오기"""
    api_key = os.environ["YOUTUBE_API_KEY"]

    # 최근 발매 아티스트 (중복 제거, 최대 10팀)
    artists_seen = []
    for r in recent_releases:
        if r["artist"] not in artists_seen:
            artists_seen.append(r["artist"])
        if len(artists_seen) >= 10:
            break

    mv_results = []

    for release in recent_releases:
        artist = release["artist"]
        title  = release["title"]

        # YouTube Search API로 MV 검색
        try:
            search_q = f"{artist} {title} MV official"
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part":       "snippet",
                    "q":          search_q,
                    "type":       "video",
                    "maxResults": 1,
                    "key":        api_key,
                },
                timeout=10,
            )
            items = r.json().get("items", [])
            if not items:
                continue
            video_id = items[0]["id"]["videoId"]

            # 조회수 가져오기
            stats_r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": video_id, "key": api_key},
                timeout=10,
            )
            stats_items = stats_r.json().get("items", [])
            if not stats_items:
                continue

            view_count = int(stats_items[0]["statistics"].get("viewCount", 0))
            mv_results.append({
                "artist":       artist,
                "title":        title,
                "video_id":     video_id,
                "views":        view_count,
                "release_date": release["release_date"],
            })

        except Exception as e:
            print(f"  YouTube search error ({artist} - {title}): {e}")

    mv_results.sort(key=lambda x: x["views"], reverse=True)
    return mv_results[:10]


def fmt_views(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# ────────────────────────────────────────────
# 4. 서문 자동 생성 (API 없이)
# ────────────────────────────────────────────

def build_intro(recent: list[dict], upcoming: list[dict], mv_data: list[dict]) -> str:
    lines = []

    if recent:
        names = ", ".join(
            f"{r['artist']} 《{r['title']}》"
            for r in recent[:3]
        )
        suffix = f" 등 총 {len(recent)}건" if len(recent) > 3 else ""
        lines.append(f"최근 30일간 {names}{suffix}이 발매됐습니다.")
    else:
        lines.append("최근 30일간 새로운 발매 소식은 없습니다.")

    if upcoming:
        next_cb = upcoming[0]
        rel     = next_cb["release_date"]
        d_day   = (datetime.date.fromisoformat(rel) - datetime.date.today()).days
        lines.append(
            f"다가오는 컴백으로는 {next_cb['artist']}의 《{next_cb['title']}》 발매가 "
            f"D-{d_day}로 예정되어 있습니다."
        )

    if mv_data:
        top = mv_data[0]
        lines.append(
            f"최근 컴백 MV 중 {top['artist']}의 〈{top['title']}〉이 "
            f"{fmt_views(top['views'])} 조회수로 선두를 달리고 있습니다."
        )

    lines.append("엔터산업 주요 동향을 아래에서 확인하세요.")
    return " ".join(lines)


# ────────────────────────────────────────────
# 5. HTML 렌더링
# ────────────────────────────────────────────

TYPE_MAP  = {"album": "정규앨범", "single": "싱글", "ep": "EP", "compilation": "컴필레이션"}
TYPE_TAG  = {"album": "tag-purple", "single": "tag-teal", "ep": "tag-blue", "compilation": "tag-amber"}
BAR_COLORS = ["#D4537E", "#378ADD", "#EF9F27", "#1D9E75", "#7F77DD",
               "#D85A30", "#639922", "#BA7517", "#E24B4A", "#1D9E75"]


def build_release_cards(recent: list[dict]) -> str:
    if not recent:
        return "<p class='empty'>최근 30일 내 신보 없음</p>"
    cards = []
    for r in recent:
        tl  = TYPE_MAP.get(r["type"], r["type"].upper())
        tc  = TYPE_TAG.get(r["type"], "tag-pink")
        cards.append(f"""
  <div class="card">
    <div class="card-row">
      <div class="card-icon">🎵</div>
      <div class="card-body">
        <div class="card-title">{r['artist']} — 《{r['title']}》</div>
        <div class="card-source">발매일 {r['release_date']} · {tl}</div>
        <div class="tags" style="margin-top:8px;">
          <span class="tag {tc}">{tl}</span>
          <a href="{r['spotify_url']}" target="_blank" class="tag tag-spotify">Spotify →</a>
        </div>
      </div>
    </div>
  </div>""")
    return "\n".join(cards)


def build_comeback_list(upcoming: list[dict]) -> str:
    if not upcoming:
        return "<p class='empty'>예정된 컴백 없음</p>"
    today = datetime.date.today()
    items = []
    for u in upcoming[:8]:
        rel    = datetime.date.fromisoformat(u["release_date"])
        d_day  = (rel - today).days
        tl     = TYPE_MAP.get(u["type"], u["type"].upper())
        d_label= f"D-{d_day}" if d_day > 0 else "오늘"
        badge_cls = "status-soon" if d_day <= 7 else "status-upcoming"
        dot_color = "#378ADD" if d_day <= 7 else "#EF9F27"
        items.append(f"""
    <div class="comeback-item">
      <div class="cb-date">{u['release_date'][5:]}</div>
      <div class="cb-dot" style="background:{dot_color};"></div>
      <div class="cb-info">
        <div class="cb-artist">{u['artist']}</div>
        <div class="cb-album">《{u['title']}》 {tl}</div>
      </div>
      <span class="status-badge {badge_cls}">{d_label}</span>
    </div>""")
    return "\n".join(items)


def build_mv_rows(mv_data: list[dict]) -> str:
    if not mv_data:
        return "<p class='empty'>MV 데이터 없음</p>"
    max_v = mv_data[0]["views"] or 1
    rows  = []
    for i, mv in enumerate(mv_data):
        pct   = int(mv["views"] / max_v * 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        yt_url= f"https://www.youtube.com/watch?v={mv['video_id']}"
        rows.append(f"""
  <div class="mv-row">
    <div class="mv-rank">{i+1}</div>
    <div class="mv-name">
      <a href="{yt_url}" target="_blank" style="color:inherit;text-decoration:none;">
        {mv['artist']} — {mv['title']}
      </a>
    </div>
    <div class="mv-track"><div class="mv-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="mv-val">{fmt_views(mv['views'])}</div>
  </div>""")
    return "\n".join(rows)


def render_html(recent, upcoming, mv_data) -> str:
    intro          = build_intro(recent, upcoming, mv_data)
    release_cards  = build_release_cards(recent)
    comeback_list  = build_comeback_list(upcoming)
    mv_rows        = build_mv_rows(mv_data)

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

  /* 헤더 */
  .header {{ padding:2.5rem 0 2rem; border-bottom:1px solid var(--border-strong); margin-bottom:2rem; }}
  .logo-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:1.25rem; }}
  .logo {{ font-family:'DM Serif Display',serif; font-size:13px; letter-spacing:.18em; text-transform:uppercase; color:var(--text-muted); }}
  .date-badge {{ font-size:11px; font-weight:500; padding:3px 10px; background:var(--accent); color:#FFF; border-radius:99px; }}
  .header h1 {{ font-family:'DM Serif Display',serif; font-size:34px; font-weight:400; line-height:1.2; margin-bottom:.5rem; }}
  .header h1 em {{ font-style:italic; color:var(--text-secondary); }}
  .header-sub {{ font-size:13px; color:var(--text-muted); }}

  /* 서문 */
  .intro {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.25rem 1.5rem; margin-bottom:2.5rem; font-size:14px; color:var(--text-secondary); line-height:1.8; }}

  /* 섹션 */
  .section {{ margin-bottom:2.5rem; }}
  .section-label {{ font-size:10px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; color:var(--text-muted); padding-bottom:.75rem; border-bottom:1px solid var(--border); margin-bottom:1rem; }}
  .empty {{ color:var(--text-muted); font-size:13px; padding:.5rem 0; }}

  /* 카드 */
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; margin-bottom:.6rem; }}
  .card-row {{ display:flex; gap:14px; align-items:flex-start; }}
  .card-icon {{ width:52px; height:52px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0; border:1px solid var(--border); }}
  .card-body {{ flex:1; min-width:0; }}
  .card-title {{ font-size:14px; font-weight:500; margin-bottom:3px; }}
  .card-source {{ font-size:11px; color:var(--text-muted); }}
  .tags {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .tag {{ font-size:11px; font-weight:500; padding:2px 9px; border-radius:99px; text-decoration:none; }}
  .tag-purple {{ background:var(--purple-bg); color:var(--purple); }}
  .tag-blue   {{ background:var(--blue-bg);   color:var(--blue); }}
  .tag-pink   {{ background:var(--pink-bg);   color:var(--pink); }}
  .tag-teal   {{ background:var(--teal-bg);   color:var(--teal); }}
  .tag-amber  {{ background:var(--amber-bg);  color:var(--amber); }}
  .tag-spotify {{ background:#E3F7F1; color:#0D6B52; }}

  /* 컴백 일정 */
  .comeback-list {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; overflow:hidden; }}
  .comeback-item {{ display:flex; align-items:center; gap:14px; padding:.85rem 1.25rem; border-bottom:1px solid var(--border); }}
  .comeback-item:last-child {{ border-bottom:none; }}
  .cb-date {{ font-size:12px; font-weight:500; color:var(--text-muted); min-width:40px; font-variant-numeric:tabular-nums; }}
  .cb-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
  .cb-info {{ flex:1; min-width:0; }}
  .cb-artist {{ font-size:14px; font-weight:500; }}
  .cb-album {{ font-size:12px; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .status-badge {{ font-size:10px; font-weight:500; padding:3px 9px; border-radius:99px; white-space:nowrap; }}
  .status-soon     {{ background:var(--blue-bg);  color:var(--blue); }}
  .status-upcoming {{ background:var(--amber-bg); color:var(--amber); }}

  /* MV 차트 */
  .mv-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .mv-row {{ display:flex; align-items:center; gap:12px; margin-bottom:10px; }}
  .mv-row:last-of-type {{ margin-bottom:0; }}
  .mv-rank {{ font-size:11px; font-weight:500; color:var(--text-muted); min-width:16px; text-align:right; }}
  .mv-name {{ font-size:13px; color:var(--text-secondary); min-width:160px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .mv-track {{ flex:1; height:5px; background:var(--bg); border-radius:99px; overflow:hidden; }}
  .mv-fill {{ height:100%; border-radius:99px; }}
  .mv-val {{ font-size:12px; font-weight:500; color:var(--text-primary); min-width:44px; text-align:right; }}
  .mv-note {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}

  /* 푸터 */
  .footer {{ border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; font-size:12px; color:var(--text-muted); display:flex; align-items:center; justify-content:space-between; }}
  .footer a {{ color:var(--text-muted); text-decoration:none; }}
  @media(max-width:540px) {{
    .header h1 {{ font-size:26px; }}
    .mv-name {{ min-width:100px; }}
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
    <div class="section-label">컴백 일정 (향후 60일)</div>
    <div class="comeback-list">
      {comeback_list}
    </div>
  </div>

  <div class="section">
    <div class="section-label">최근 컴백 MV 조회수 순위</div>
    <div class="mv-card">
      {mv_rows}
      <div class="mv-note">* 최근 30일 내 발매 MV 기준 · 유튜브 조회수 · 매일 오전 8시 자동 업데이트</div>
    </div>
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

    print("  → Spotify 신보/컴백 조회 중...")
    token          = get_spotify_token()
    recent, upcoming = fetch_releases(token)
    print(f"     최근 발매 {len(recent)}건 / 예정 {len(upcoming)}건")

    print("  → YouTube 최근 컴백 MV 조회수 수집 중...")
    mv_data = fetch_recent_mv_views(recent)
    print(f"     MV {len(mv_data)}건 수집")

    print("  → HTML 렌더링 중...")
    html = render_html(recent, upcoming, mv_data)

    output_path = OUTPUT_DIR / f"{TODAY}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  → 완료: {output_path}")


if __name__ == "__main__":
    main()
