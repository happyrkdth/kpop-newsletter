"""
K-pop Intelligence Newsletter Generator
매일 GitHub Actions에서 자동 실행됩니다.

필요한 환경변수 (GitHub Secrets):
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  YOUTUBE_API_KEY
"""

import os
import re
import datetime
import requests
from pathlib import Path
from urllib.parse import quote

try:
    import feedparser
except ImportError:
    feedparser = None


# ────────────────────────────────────────────
# 0. 설정
# ────────────────────────────────────────────

TODAY  = datetime.date.today().isoformat()
DAY_KO = ["월", "화", "수", "목", "금", "토", "일"][datetime.date.today().weekday()]
OUTPUT_DIR = Path("newsletters")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── 기획사 공식 YouTube 채널 ──────────────────
# role별 설명:
#   Agency_Consolidated : 기획사 통합 채널 (HYBE LABELS, SMTOWN 등)
#   Agency              : 기획사 자체 채널
#   Distributor         : 유통사 채널 (1theK, Stone Music 등)
LABEL_CHANNELS = [
    {"name": "HYBE LABELS",           "role": "Agency_Consolidated", "channel_id": "UC3IZK6nSKSafO09p2pEqU_Q"},
    {"name": "SMTOWN",                 "role": "Agency_Consolidated", "channel_id": "UCEf_Bc-KVd7onSeifS3k9hw"},
    {"name": "JYP Entertainment",      "role": "Agency_Consolidated", "channel_id": "UCaO65SiL97GaJDqhVQSis7g"},
    {"name": "YG Entertainment",       "role": "Agency_Consolidated", "channel_id": "UC07-dOwgza1vXWsh2UfAs4Q"},
    {"name": "Starship Entertainment", "role": "Agency",              "channel_id": "UCG70K_An9HshY6C0FfM4aA"},
    {"name": "THE BLACK LABEL",        "role": "Agency",              "channel_id": "UCwcubL6D8S_p_OtoH24U_Mg"},
    {"name": "CUBE Entertainment",     "role": "Agency",              "channel_id": "UCritGHo7Yz9nn_Wdm4_F-9A"},
    {"name": "1theK",                  "role": "Distributor",         "channel_id": "UCweOkHszguqKYSbaM6qZ5GQ"},
    {"name": "Stone Music Entertainment","role": "Distributor",       "channel_id": "UC_p55Sg4mK_uR7_6961S-rA"},
    {"name": "Genie Music",            "role": "Distributor",         "channel_id": "UC_o6p6D6uRL3uM_VfXN_T_A"},
]

# ── 아티스트 목록 (Spotify 신보 감지용) ───────
ARTISTS = {
    "BLACKPINK":   {"spotify_id": "41MozSoPIsD1dJM0CLPjZF", "label": "YG 엔터테인먼트"},
    "IVE":         {"spotify_id": "6RHTUrRF63xao58xh9FXYJ", "label": "스타쉽 엔터테인먼트"},
    "NewJeans":    {"spotify_id": "2NZVRjbzIDfuSE6ESWJvvU", "label": "ADOR (HYBE)"},
    "SEVENTEEN":   {"spotify_id": "7nqOGox5dQiUgmxGUCjkjh", "label": "PLEDIS (HYBE)"},
    "Stray Kids":  {"spotify_id": "2b4LTnUMBB34DWnFMKVEDP", "label": "JYP 엔터테인먼트"},
    "aespa":       {"spotify_id": "2cnMpRsRX83sFl96xKXQ1",  "label": "SM 엔터테인먼트"},
    "IU":          {"spotify_id": "3HqSZScBaE9dy3ySJpq0kk", "label": "EDAM 엔터테인먼트"},
    "Jennie":      {"spotify_id": "1Oa0bMld0A3u5N5eRMVLbk", "label": "OA (ODD ATELIER)"},
    "Rosé":        {"spotify_id": "2euSnPTJ3HgDhcfajnFmad", "label": "더블랙레이블"},
    "(G)I-DLE":    {"spotify_id": "2AfmfGFAFZaECNxqR2QKEZ", "label": "큐브 엔터테인먼트"},
    "Lisa":        {"spotify_id": "5DnBaQWjfBM69RQHX47aKr", "label": "LLOUD"},
    "RIIZE":       {"spotify_id": "4PbOQFdGJJHu25UMZ1sTDR", "label": "SM 엔터테인먼트"},
    "ILLIT":       {"spotify_id": "3GjN0Vc5AkRBGAMuRXhaDI", "label": "BELIFT LAB (HYBE)"},
    "Red Velvet":  {"spotify_id": "1z4g3DjTBBZKhvAroFlhOM", "label": "SM 엔터테인먼트"},
    "G-DRAGON":    {"spotify_id": "5p5kkpXNUJsqBksBbdoWMB", "label": "갤럭시코퍼레이션"},
    "BTS":         {"spotify_id": "3Nrfpe0tUJi4K4DXYWgMUX", "label": "빅히트 뮤직 (HYBE)"},
    "TWICE":       {"spotify_id": "7n2Ycct7Beij7Dj7meI4X0", "label": "JYP 엔터테인먼트"},
    "NMIXX":       {"spotify_id": "1tmxpdDbyKoCOXlSb7MGFU", "label": "JYP 엔터테인먼트"},
    "ENHYPEN":     {"spotify_id": "0bktO5A1yBhMVTXXbQEjxW", "label": "BELIFT LAB (HYBE)"},
    "TXT":         {"spotify_id": "4vGrte8FDu062Ntj0RsPiZ", "label": "빅히트 뮤직 (HYBE)"},
    "ATEEZ":       {"spotify_id": "1Cd373x7Nf6QEHBHB7DNVG", "label": "KQ 엔터테인먼트"},
    "LE SSERAFIM": {"spotify_id": "6HvZYsbFfjnjFrWF950C9d", "label": "SOURCE MUSIC (HYBE)"},
    "BINI":        {"spotify_id": "6MdRFpKXAMbBr88b1T3UM7", "label": "Star Music (Philippines)"},
}

TYPE_MAP = {
    "album":       ("정규앨범", "tag-purple"),
    "single":      ("싱글",    "tag-teal"),
    "ep":          ("미니앨범", "tag-blue"),
    "compilation": ("컴필레이션","tag-amber"),
}
BAR_COLORS = ["#D4537E","#378ADD","#EF9F27","#1D9E75","#7F77DD",
               "#D85A30","#639922","#BA7517","#E24B4A","#5DCAA5"]


# ────────────────────────────────────────────
# 1. Spotify
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


def fetch_recent_releases(token: str, days: int = 90) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    today   = datetime.date.today()
    cutoff  = today - datetime.timedelta(days=days)
    recent, seen = [], set()

    for artist_name, info in ARTISTS.items():
        try:
            r = requests.get(
                f"https://api.spotify.com/v1/artists/{info['spotify_id']}/albums",
                headers=headers,
                params={"album_type": "album,single,ep", "limit": 10, "market": "KR"},
                timeout=10,
            )
            ar = requests.get(
                f"https://api.spotify.com/v1/artists/{info['spotify_id']}",
                headers=headers, timeout=10,
            )
            genres = ar.json().get("genres", [])

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
                if cutoff <= rel_date <= today:
                    raw_type   = album["album_type"]
                    type_ko, _ = TYPE_MAP.get(raw_type, (raw_type.upper(), "tag-pink"))
                    recent.append({
                        "artist":       artist_name,
                        "label":        info["label"],
                        "title":        album["name"],
                        "type":         raw_type,
                        "type_ko":      type_ko,
                        "release_date": raw[:10],
                        "spotify_url":  album["external_urls"]["spotify"],
                        "total_tracks": album.get("total_tracks", 0),
                        "genres":       genres[:3],
                    })
        except Exception as e:
            print(f"  Spotify error ({artist_name}): {e}")

    recent.sort(key=lambda x: x["release_date"], reverse=True)
    return recent


# ────────────────────────────────────────────
# 2. YouTube: 기획사 공식 채널 기반 MV 조회수
# ────────────────────────────────────────────

def fetch_official_mv_views(recent_releases: list[dict]) -> list[dict]:
    """
    최근 발매 아티스트명으로 기획사 공식 채널을 검색해
    공식 MV 조회수를 가져옴.
    Agency_Consolidated → Agency → Distributor 순으로 시도.
    """
    api_key    = os.environ["YOUTUBE_API_KEY"]
    mv_results = []
    seen_titles= set()
    MV_KEYWORDS= ["MV", "M/V", "MUSIC VIDEO", "뮤직비디오", "OFFICIAL VIDEO"]

    # 채널 우선순위 정렬
    priority = {"Agency_Consolidated": 0, "Agency": 1, "Distributor": 2}
    channels = sorted(LABEL_CHANNELS, key=lambda x: priority.get(x["role"], 9))

    for release in recent_releases:
        query_key = (release["artist"], release["title"])
        if query_key in seen_titles:
            continue

        found = False
        for ch in channels:
            if found:
                break
            try:
                r = requests.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part":      "snippet",
                        "channelId": ch["channel_id"],
                        "q":         f"{release['artist']} {release['title']}",
                        "type":      "video",
                        "order":     "date",
                        "maxResults": 5,
                        "key":       api_key,
                    },
                    timeout=10,
                )
                items = r.json().get("items", [])
                if not items:
                    continue

                video_id = None
                for item in items:
                    vtitle = item["snippet"]["title"].upper()
                    if any(kw in vtitle for kw in MV_KEYWORDS):
                        video_id = item["id"]["videoId"]
                        break
                if not video_id:
                    video_id = items[0]["id"]["videoId"]

                stats_r = requests.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={"part": "statistics", "id": video_id, "key": api_key},
                    timeout=10,
                )
                stats_items = stats_r.json().get("items", [])
                if not stats_items:
                    continue

                view_count = int(stats_items[0]["statistics"].get("viewCount", 0))
                if view_count == 0:
                    continue

                mv_results.append({
                    "artist":       release["artist"],
                    "title":        release["title"],
                    "video_id":     video_id,
                    "views":        view_count,
                    "channel_name": ch["name"],
                    "release_date": release["release_date"],
                })
                seen_titles.add(query_key)
                found = True

            except Exception as e:
                print(f"  YouTube error ({ch['name']} / {release['artist']}): {e}")

    mv_results.sort(key=lambda x: x["views"], reverse=True)
    return mv_results[:10]


def fmt_views(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.1f}M"
    if n >= 1_000:         return f"{n/1_000:.0f}K"
    return str(n)


# ────────────────────────────────────────────
# 3. 멜론 차트 TOP 10
# ────────────────────────────────────────────

def fetch_melon_chart(top_n: int = 10) -> list[dict]:
    """멜론 실시간 차트 TOP 10"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.melon.com/",
        }
        r = requests.get(
            "https://www.melon.com/chart/index.htm",
            headers=headers,
            timeout=15,
        )
        html = r.text

        # 멜론 차트 파싱: 곡명, 아티스트
        songs   = re.findall(r'<div class="ellipsis rank01">\s*<span>\s*<a[^>]*>(.*?)</a>', html)
        artists = re.findall(r'<div class="ellipsis rank02">\s*<span[^>]*>(.*?)</span>', html)

        results = []
        for i, (song, artist) in enumerate(zip(songs[:top_n], artists[:top_n]), 1):
            song_clean   = re.sub(r"<[^>]+>", "", song).strip()
            artist_clean = re.sub(r"<[^>]+>", "", artist).strip()
            if song_clean and artist_clean:
                results.append({"rank": i, "title": song_clean, "artist": artist_clean})

        if results:
            return results

        # 대체 파싱
        blocks = re.findall(
            r'data-song-no[^>]*>.*?class="ellipsis rank01"[^>]*>\s*<span>\s*<a[^>]*>(.*?)</a>.*?'
            r'class="ellipsis rank02"[^>]*>\s*<span[^>]*>(.*?)</span>',
            html, re.DOTALL
        )
        return [
            {"rank": i, "title": re.sub(r"<[^>]+>", "", s).strip(),
             "artist": re.sub(r"<[^>]+>", "", a).strip()}
            for i, (s, a) in enumerate(blocks[:top_n], 1)
            if re.sub(r"<[^>]+>", "", s).strip()
        ]

    except Exception as e:
        print(f"  Melon chart error: {e}")
        return []


# ────────────────────────────────────────────
# 4. 구글 뉴스 RSS: 엔터/케이팝 뉴스 (클릭 → 원문)
# ────────────────────────────────────────────

def fetch_kpop_news(max_items: int = 10) -> list[dict]:
    """
    구글 뉴스 RSS로 케이팝/엔터 관련 뉴스 수집.
    클릭 시 원문으로 바로 연결.
    """
    if feedparser is None:
        print("  feedparser 없음")
        return []

    # 구글 뉴스 RSS - 한국어 케이팝/엔터 키워드
    QUERIES = [
        "케이팝 컴백",
        "K-pop 신보",
        "아이돌 앨범",
        "케이팝 차트",
        "엔터테인먼트 음악",
    ]

    seen, articles = set(), []

    for query in QUERIES:
        if len(articles) >= max_items:
            break
        try:
            encoded = quote(query)
            url = (
                f"https://news.google.com/rss/search"
                f"?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
            )
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if len(articles) >= max_items:
                    break
                title = entry.get("title", "").strip()
                # 구글 뉴스 제목 형식: "기사제목 - 언론사" → 분리
                if " - " in title:
                    headline, source = title.rsplit(" - ", 1)
                else:
                    headline, source = title, ""

                link = entry.get("link", "")
                desc = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
                summary = desc[:120] + "..." if len(desc) > 120 else desc
                pub_date = entry.get("published", "")[:10]

                if headline in seen or not headline:
                    continue
                seen.add(headline)

                articles.append({
                    "title":   headline,
                    "source":  source,
                    "url":     link,
                    "summary": summary,
                    "date":    pub_date,
                })
        except Exception as e:
            print(f"  Google News RSS error ({query}): {e}")

    return articles[:max_items]


# ────────────────────────────────────────────
# 5. 서문 생성
# ────────────────────────────────────────────

def build_intro(recent, mv_data, chart) -> str:
    lines = []
    if recent:
        names  = ", ".join(f"{r['artist']} 《{r['title']}》" for r in recent[:2])
        suffix = f" 등 총 {len(recent)}건" if len(recent) > 2 else ""
        lines.append(f"최근 90일간 {names}{suffix}이 발매됐습니다.")
    else:
        lines.append("최근 90일간 등록된 아티스트의 새로운 발매 소식은 없습니다.")
    if chart:
        lines.append(f"멜론 차트 1위는 {chart[0]['artist']}의 〈{chart[0]['title']}〉입니다.")
    if mv_data:
        top = mv_data[0]
        lines.append(
            f"최근 컴백 MV 중 {top['artist']}의 〈{top['title']}〉이 "
            f"{fmt_views(top['views'])} 조회수로 선두입니다."
        )
    lines.append("엔터산업 주요 동향을 아래에서 확인하세요.")
    return " ".join(lines)


# ────────────────────────────────────────────
# 6. HTML 빌더
# ────────────────────────────────────────────

def build_release_cards(recent: list[dict]) -> str:
    if not recent:
        return "<p class='empty'>최근 90일 내 신보 없음</p>"
    cards = []
    for r in recent:
        _, tag_cls = TYPE_MAP.get(r["type"], (r["type"], "tag-pink"))
        genre_tags = "".join(f'<span class="tag tag-gray">{g}</span>' for g in r["genres"])
        meta = " · ".join(p for p in [r["label"], f"{r['total_tracks']}트랙" if r["total_tracks"] else ""] if p)
        cards.append(f"""
  <div class="card">
    <div class="card-row">
      <div class="card-icon">🎵</div>
      <div class="card-body">
        <div class="card-title">{r['artist']} — 《{r['title']}》</div>
        <div class="card-source">{r['release_date']} · {r['type_ko']} · {meta}</div>
        <div class="tags" style="margin-top:8px;">
          <span class="tag {tag_cls}">{r['type_ko']}</span>
          {genre_tags}
          <a href="{r['spotify_url']}" target="_blank" class="tag tag-spotify">Spotify →</a>
        </div>
      </div>
    </div>
  </div>""")
    return "\n".join(cards)


def build_mv_rows(mv_data: list[dict]) -> str:
    if not mv_data:
        return "<p class='empty'>최근 컴백 공식 MV 데이터 없음</p>"
    max_v = mv_data[0]["views"] or 1
    rows  = []
    for i, mv in enumerate(mv_data):
        pct    = int(mv["views"] / max_v * 100)
        color  = BAR_COLORS[i % len(BAR_COLORS)]
        yt_url = f"https://www.youtube.com/watch?v={mv['video_id']}"
        rows.append(f"""
  <div class="mv-row">
    <div class="mv-rank">{i+1}</div>
    <div class="mv-name">
      <a href="{yt_url}" target="_blank" style="color:inherit;text-decoration:none;">
        {mv['artist']} — {mv['title']}
      </a>
      <span class="mv-ch">via {mv['channel_name']}</span>
    </div>
    <div class="mv-track"><div class="mv-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="mv-val">{fmt_views(mv['views'])}</div>
  </div>""")
    return "\n".join(rows)


def build_chart_rows(chart: list[dict]) -> str:
    if not chart:
        return "<p class='empty'>멜론 차트 데이터를 가져오지 못했습니다</p>"
    rows = []
    max_n = len(chart)
    for item in chart:
        bar_pct = int((max_n - item["rank"] + 1) / max_n * 100)
        color   = BAR_COLORS[(item["rank"] - 1) % len(BAR_COLORS)]
        badge   = ""
        if item["rank"] == 1:   badge = '<span class="rank-badge rank-1">1위</span>'
        elif item["rank"] == 2: badge = '<span class="rank-badge rank-2">2위</span>'
        elif item["rank"] == 3: badge = '<span class="rank-badge rank-3">3위</span>'
        rows.append(f"""
  <div class="chart-row">
    <div class="chart-rank">{item['rank']}</div>
    <div class="chart-info">
      <div class="chart-title">{item['title']} {badge}</div>
      <div class="chart-artist">{item['artist']}</div>
    </div>
    <div class="chart-bar-wrap">
      <div class="chart-bar-track">
        <div class="chart-bar-fill" style="width:{bar_pct}%;background:{color};"></div>
      </div>
    </div>
  </div>""")
    return "\n".join(rows)


def build_news_cards(articles: list[dict]) -> str:
    if not articles:
        return "<p class='empty'>뉴스를 가져오지 못했습니다</p>"
    cards = []
    for a in articles:
        source_str = f"{a['source']}" if a["source"] else "뉴스"
        date_str   = f" · {a['date']}" if a["date"] else ""
        cards.append(f"""
  <a class="news-card" href="{a['url']}" target="_blank">
    <div class="news-meta">{source_str}{date_str} <span class="ext-arrow">↗</span></div>
    <div class="news-title">{a['title']}</div>
    <div class="news-summary">{a['summary']}</div>
  </a>""")
    return "\n".join(cards)


# ────────────────────────────────────────────
# 7. HTML 렌더링
# ────────────────────────────────────────────

def render_html(recent, mv_data, chart, news) -> str:
    intro         = build_intro(recent, mv_data, chart)
    release_cards = build_release_cards(recent)
    mv_rows       = build_mv_rows(mv_data)
    chart_rows    = build_chart_rows(chart)
    news_cards    = build_news_cards(news)

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
  .intro {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.25rem 1.5rem; margin-bottom:2.5rem; font-size:14px; color:var(--text-secondary); line-height:1.8; }}
  .section {{ margin-bottom:2.5rem; }}
  .section-label {{ font-size:10px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; color:var(--text-muted); padding-bottom:.75rem; border-bottom:1px solid var(--border); margin-bottom:1rem; }}
  .empty {{ color:var(--text-muted); font-size:13px; padding:.5rem 0; }}

  /* 신보 카드 */
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; margin-bottom:.6rem; }}
  .card-row {{ display:flex; gap:14px; align-items:flex-start; }}
  .card-icon {{ width:52px; height:52px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0; border:1px solid var(--border); }}
  .card-body {{ flex:1; min-width:0; }}
  .card-title {{ font-size:14px; font-weight:500; margin-bottom:3px; }}
  .card-source {{ font-size:11px; color:var(--text-muted); margin-bottom:2px; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .tag {{ font-size:11px; font-weight:500; padding:2px 9px; border-radius:99px; text-decoration:none; display:inline-block; }}
  .tag-purple  {{ background:var(--purple-bg); color:var(--purple); }}
  .tag-blue    {{ background:var(--blue-bg);   color:var(--blue); }}
  .tag-pink    {{ background:var(--pink-bg);   color:var(--pink); }}
  .tag-teal    {{ background:var(--teal-bg);   color:var(--teal); }}
  .tag-amber   {{ background:var(--amber-bg);  color:var(--amber); }}
  .tag-gray    {{ background:#EDECE8; color:#5C5B57; }}
  .tag-spotify {{ background:#E3F7F1; color:#0D6B52; }}

  /* MV 차트 */
  .mv-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .mv-row {{ display:flex; align-items:center; gap:10px; margin-bottom:12px; }}
  .mv-row:last-of-type {{ margin-bottom:0; }}
  .mv-rank {{ font-size:11px; font-weight:500; color:var(--text-muted); min-width:16px; text-align:right; flex-shrink:0; }}
  .mv-name {{ font-size:13px; color:var(--text-secondary); flex:1; min-width:0; }}
  .mv-ch {{ display:block; font-size:10px; color:var(--text-muted); margin-top:1px; }}
  .mv-track {{ width:80px; height:5px; background:var(--bg); border-radius:99px; overflow:hidden; flex-shrink:0; }}
  .mv-fill {{ height:100%; border-radius:99px; }}
  .mv-val {{ font-size:12px; font-weight:500; color:var(--text-primary); min-width:44px; text-align:right; flex-shrink:0; }}
  .mv-note {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}

  /* 차트 */
  .chart-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .chart-row {{ display:flex; align-items:center; gap:12px; padding:.6rem 0; border-bottom:1px solid var(--border); }}
  .chart-row:last-child {{ border-bottom:none; }}
  .chart-rank {{ font-size:13px; font-weight:500; color:var(--text-muted); min-width:20px; text-align:center; flex-shrink:0; }}
  .chart-info {{ flex:1; min-width:0; }}
  .chart-title {{ font-size:14px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .chart-artist {{ font-size:12px; color:var(--text-muted); }}
  .chart-bar-wrap {{ width:80px; flex-shrink:0; }}
  .chart-bar-track {{ height:4px; background:var(--bg); border-radius:99px; overflow:hidden; }}
  .chart-bar-fill {{ height:100%; border-radius:99px; }}
  .rank-badge {{ font-size:10px; font-weight:500; padding:1px 6px; border-radius:99px; margin-left:5px; vertical-align:middle; }}
  .rank-1 {{ background:#FDF0D8; color:#7A4B08; }}
  .rank-2 {{ background:#EDECE8; color:#5C5B57; }}
  .rank-3 {{ background:#FAEAF2; color:#9A2E5E; }}
  .chart-source {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}

  /* 뉴스 카드 — 클릭 가능한 <a> 태그 */
  .news-card {{
    display:block; text-decoration:none;
    background:var(--surface); border:1px solid var(--border);
    border-radius:14px; padding:1rem 1.25rem; margin-bottom:.6rem;
    transition:border-color .1s, background .1s;
  }}
  .news-card:hover {{ border-color:rgba(0,0,0,.22); background:#FAFAF8; }}
  .news-meta {{ font-size:10px; font-weight:500; letter-spacing:.08em; color:var(--text-muted); margin-bottom:4px; display:flex; align-items:center; gap:4px; }}
  .ext-arrow {{ font-size:11px; color:var(--text-muted); margin-left:auto; }}
  .news-title {{ font-size:14px; font-weight:500; color:var(--text-primary); line-height:1.45; margin-bottom:5px; }}
  .news-summary {{ font-size:12px; color:var(--text-secondary); line-height:1.55; }}

  .footer {{ border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; font-size:12px; color:var(--text-muted); display:flex; align-items:center; justify-content:space-between; }}
  .footer a {{ color:var(--text-muted); text-decoration:none; }}
  @media(max-width:540px) {{
    .header h1 {{ font-size:26px; }}
    .mv-track {{ width:50px; }}
    .chart-bar-wrap {{ width:50px; }}
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
    <div class="section-label">신보 발매 소식 (최근 90일)</div>
    {release_cards}
  </div>

  <div class="section">
    <div class="section-label">최근 컴백 MV 조회수 — 기획사 공식 채널 기준</div>
    <div class="mv-card">
      {mv_rows}
      <div class="mv-note">* 최근 90일 내 발매 · HYBE / SM / JYP / YG 등 기획사 공식 채널 기준 · 매일 오전 8시 업데이트</div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">멜론 실시간 차트 TOP 10</div>
    <div class="chart-card">
      {chart_rows}
      <div class="chart-source">* 멜론(Melon) 실시간 차트 기준 · 매일 오전 8시 업데이트</div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">케이팝 주요 뉴스 (최대 10건)</div>
    {news_cards}
  </div>

  <div class="footer">
    <span>K-pop Intelligence · 매일 자동 업데이트</span>
    <span><a href="../index.html">← 최신호</a> · <a href="../archive.html">아카이브</a></span>
  </div>

</div>
</body>
</html>"""


# ────────────────────────────────────────────
# 8. 메인 실행
# ────────────────────────────────────────────

def main():
    print(f"[{TODAY}] K-pop Intelligence 생성 시작...")

    print("  → Spotify 신보 조회 중...")
    token  = get_spotify_token()
    recent = fetch_recent_releases(token, days=90)
    print(f"     최근 발매 {len(recent)}건")

    print("  → YouTube 기획사 공식 채널 MV 조회수 수집 중...")
    mv_data = fetch_official_mv_views(recent)
    print(f"     MV {len(mv_data)}건")

    print("  → 멜론 차트 수집 중...")
    chart = fetch_melon_chart(top_n=10)
    print(f"     차트 {len(chart)}위까지 수집")

    print("  → 케이팝 뉴스 수집 중...")
    news = fetch_kpop_news(max_items=10)
    print(f"     뉴스 {len(news)}건")

    print("  → HTML 렌더링 중...")
    html = render_html(recent, mv_data, chart, news)

    output_path = OUTPUT_DIR / f"{TODAY}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  → 완료: {output_path}")


if __name__ == "__main__":
    main()
