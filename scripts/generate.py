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


# ── 아티스트 목록 ──────────────────────────
# spotify_id : Spotify 아티스트 ID
# yt_channel : 공식 YouTube 채널 ID  (채널 페이지 주소의 /channel/ 뒤 or @채널명 클릭 후 주소창)
# label      : 소속사
ARTISTS = {
    "aespa": {
        "spotify_id": "2cnMpRsRX83sFl96xKXQ1",
        "yt_channel": "UCrFd2TMQFJ3gLwBKvgBBUSA",
        "label": "SM 엔터테인먼트",
    },
    "SEVENTEEN": {
        "spotify_id": "7nqOGox5dQiUgmxGUCjkjh",
        "yt_channel": "UCfOuBOBrSNkdGajg2bKFxCg",
        "label": "PLEDIS (HYBE)",
    },
    "ILLIT": {
        "spotify_id": "3GjN0Vc5AkRBGAMuRXhaDI",
        "yt_channel": "UCDe-HgMKiXAT4yCQPsWJlOw",
        "label": "BELIFT LAB (HYBE)",
    },
    "NewJeans": {
        "spotify_id": "2NZVRjbzIDfuSE6ESWJvvU",
        "yt_channel": "UC5g6gB-RFvPWPfkP9EjXhbw",
        "label": "ADOR (HYBE)",
    },
    "BINI": {
        "spotify_id": "6MdRFpKXAMbBr88b1T3UM7",
        "yt_channel": "UCQsqCLsFMiWMqRdFwOJdxOA",
        "label": "Star Music (Philippines)",
    },
    "NMIXX": {
        "spotify_id": "1tmxpdDbyKoCOXlSb7MGFU",
        "yt_channel": "UCK8f4VbTuuoNQiXnVA6HPUQ",
        "label": "JYP 엔터테인먼트",
    },
    "LE SSERAFIM": {
        "spotify_id": "6HvZYsbFfjnjFrWF950C9d",
        "yt_channel": "UCmKdgKFU3xEkv1SrHbkwivg",
        "label": "SOURCE MUSIC (HYBE)",
    },
    "IVE": {
        "spotify_id": "6RHTUrRF63xao58xh9FXYJ",
        "yt_channel": "UCpPNhPSEpf3jbKFiMUkRMTQ",
        "label": "스타쉽 엔터테인먼트",
    },
    "TWICE": {
        "spotify_id": "7n2Ycct7Beij7Dj7meI4X0",
        "yt_channel": "UCuM6bZ4govHfQxSQCNOJntw",
        "label": "JYP 엔터테인먼트",
    },
    "Stray Kids": {
        "spotify_id": "2b4LTnUMBB34DWnFMKVEDP",
        "yt_channel": "UCOP9IPO3bZBCm8T8NQIE8pQ",
        "label": "JYP 엔터테인먼트",
    },
    "ENHYPEN": {
        "spotify_id": "0bktO5A1yBhMVTXXbQEjxW",
        "yt_channel": "UCw6pFJaHDLZKVRPkCqBBCJA",
        "label": "BELIFT LAB (HYBE)",
    },
    "TXT": {
        "spotify_id": "4vGrte8FDu062Ntj0RsPiZ",
        "yt_channel": "UCbE29ptYiAeE5xOjB8qsUYA",
        "label": "빅히트 뮤직 (HYBE)",
    },
    "ATEEZ": {
        "spotify_id": "1Cd373x7Nf6QEHBHB7DNVG",
        "yt_channel": "UCv-dHNnjiqBSNLRWsq6zP1w",
        "label": "KQ 엔터테인먼트",
    },
    "BLACKPINK": {
        "spotify_id": "41MozSoPIsD1dJM0CLPjZF",
        "yt_channel": "UCOmHUn--16B90oW2L6FRR3A",
        "label": "YG 엔터테인먼트",
    },
    "BTS": {
        "spotify_id": "3Nrfpe0tUJi4K4DXYWgMUX",
        "yt_channel": "UCLkAepWjdylmXSltofFvsYQ",
        "label": "빅히트 뮤직 (HYBE)",
    },
    # 추가 형식:
    # "아티스트명": {
    #     "spotify_id": "...",
    #     "yt_channel": "...",
    #     "label": "소속사",
    # },
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
# 2. Spotify: 최근 30일 신보
# ────────────────────────────────────────────

def fetch_recent_releases(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    today   = datetime.date.today()
    past_30 = today - datetime.timedelta(days=30)
    recent  = []
    seen    = set()

    for artist_name, info in ARTISTS.items():
        try:
            # 앨범 목록
            r = requests.get(
                f"https://api.spotify.com/v1/artists/{info['spotify_id']}/albums",
                headers=headers,
                params={"album_type": "album,single,ep", "limit": 10, "market": "KR"},
                timeout=10,
            )
            # 아티스트 장르
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

                if past_30 <= rel_date <= today:
                    raw_type       = album["album_type"]
                    type_ko, _     = TYPE_MAP.get(raw_type, (raw_type.upper(), "tag-pink"))
                    total_tracks   = album.get("total_tracks", 0)
                    recent.append({
                        "artist":       artist_name,
                        "label":        info["label"],
                        "title":        album["name"],
                        "type":         raw_type,
                        "type_ko":      type_ko,
                        "release_date": raw[:10],
                        "spotify_url":  album["external_urls"]["spotify"],
                        "total_tracks": total_tracks,
                        "genres":       genres[:3],
                    })
        except Exception as e:
            print(f"  Spotify error ({artist_name}): {e}")

    recent.sort(key=lambda x: x["release_date"], reverse=True)
    return recent


# ────────────────────────────────────────────
# 3. YouTube: 공식 채널 MV 조회수
# ────────────────────────────────────────────

def fetch_official_mv_views(recent_releases: list[dict]) -> list[dict]:
    api_key      = os.environ["YOUTUBE_API_KEY"]
    mv_results   = []
    seen_artists = set()
    MV_KEYWORDS  = ["MV", "M/V", "MUSIC VIDEO", "뮤직비디오", "OFFICIAL VIDEO"]

    for release in recent_releases:
        artist = release["artist"]
        if artist in seen_artists:
            continue
        seen_artists.add(artist)

        yt_channel = ARTISTS.get(artist, {}).get("yt_channel", "")
        if not yt_channel:
            continue

        try:
            # 공식 채널에서 앨범 타이틀 관련 영상 검색
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part":      "snippet",
                    "channelId": yt_channel,
                    "q":         release["title"],
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

            # MV 키워드 포함 영상 우선 선택
            video_id = None
            for item in items:
                vtitle = item["snippet"]["title"].upper()
                if any(kw in vtitle for kw in MV_KEYWORDS):
                    video_id = item["id"]["videoId"]
                    break
            if not video_id:
                video_id = items[0]["id"]["videoId"]

            # 조회수
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
                "title":        release["title"],
                "video_id":     video_id,
                "views":        view_count,
                "release_date": release["release_date"],
            })

        except Exception as e:
            print(f"  YouTube error ({artist}): {e}")

    mv_results.sort(key=lambda x: x["views"], reverse=True)
    return mv_results[:10]


def fmt_views(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.1f}M"
    if n >= 1_000:         return f"{n/1_000:.0f}K"
    return str(n)


# ────────────────────────────────────────────
# 4. 네이버 뉴스 RSS: 케이팝 뉴스
# ────────────────────────────────────────────

def fetch_naver_kpop_news(max_items: int = 8) -> list[dict]:
    """네이버 뉴스 RSS에서 케이팝 관련 뉴스 수집"""
    if feedparser is None:
        print("  feedparser 없음")
        return []

    # 네이버 뉴스 RSS - 케이팝/아이돌/엔터 키워드
    RSS_QUERIES = [
        ("케이팝", "https://news.naver.com/rss/search?query=%EC%BC%80%EC%9D%B4%ED%8C%9D&type=0"),
        ("아이돌", "https://news.naver.com/rss/search?query=%EC%95%84%EC%9D%B4%EB%8F%8C&type=0"),
        ("K팝",   "https://news.naver.com/rss/search?query=K%ED%8C%9D&type=0"),
    ]

    seen    = set()
    articles= []

    for query_name, url in RSS_QUERIES:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "")
                desc  = entry.get("description", entry.get("summary", ""))

                # HTML 태그 제거
                desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                # 요약 100자 제한
                summary = desc_clean[:100] + "..." if len(desc_clean) > 100 else desc_clean

                if title in seen:
                    continue
                seen.add(title)

                articles.append({
                    "title":   title,
                    "url":     link,
                    "summary": summary,
                    "date":    entry.get("published", "")[:10],
                })

                if len(articles) >= max_items:
                    break
        except Exception as e:
            print(f"  Naver RSS error ({query_name}): {e}")

        if len(articles) >= max_items:
            break

    return articles[:max_items]


# ────────────────────────────────────────────
# 5. 서클차트 순위 스크래핑
# ────────────────────────────────────────────

def fetch_circle_chart(top_n: int = 10) -> list[dict]:
    """서클차트 디지털 종합 주간 차트 스크래핑"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(
            "https://circlechart.kr/page_chart/onChart.circle"
            "?nationGbn=T&targetTime=2026&hitYear=2026&termGbn=week&rankCount=10",
            headers=headers,
            timeout=15,
        )
        html = r.text

        # 서클차트 HTML 파싱 (순위, 곡명, 아티스트 추출)
        # tr.ranking 태그에서 순위 데이터 파싱
        pattern = re.compile(
            r'<td[^>]*class="[^"]*chart_num[^"]*"[^>]*>\s*(\d+)\s*</td>'
            r'.*?<div[^>]*class="[^"]*artist[^"]*"[^>]*>(.*?)</div>'
            r'.*?<div[^>]*class="[^"]*song[^"]*"[^>]*>(.*?)</div>',
            re.DOTALL,
        )
        matches = pattern.findall(html)

        if matches:
            results = []
            for rank, artist, song in matches[:top_n]:
                results.append({
                    "rank":   int(rank),
                    "artist": re.sub(r"<[^>]+>", "", artist).strip(),
                    "title":  re.sub(r"<[^>]+>", "", song).strip(),
                })
            return results

        # 패턴 매칭 실패 시 간단한 대체 파싱 시도
        rows = re.findall(r'<tr[^>]*class="[^"]*ranking[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
        results = []
        for i, row in enumerate(rows[:top_n], 1):
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(tds) >= 3:
                artist = re.sub(r"<[^>]+>", "", tds[1]).strip()
                title  = re.sub(r"<[^>]+>", "", tds[2]).strip()
                if artist and title:
                    results.append({"rank": i, "artist": artist, "title": title})
        return results

    except Exception as e:
        print(f"  Circle chart error: {e}")
        return []


# ────────────────────────────────────────────
# 6. 서문 생성
# ────────────────────────────────────────────

def build_intro(recent, mv_data, chart) -> str:
    lines = []

    if recent:
        names  = ", ".join(f"{r['artist']} 《{r['title']}》" for r in recent[:2])
        suffix = f" 등 총 {len(recent)}건" if len(recent) > 2 else ""
        lines.append(f"최근 30일간 {names}{suffix}이 발매됐습니다.")
    else:
        lines.append("최근 30일간 등록된 아티스트의 새로운 발매 소식은 없습니다.")

    if chart:
        top = chart[0]
        lines.append(f"이번 주 서클차트 1위는 {top['artist']}의 〈{top['title']}〉입니다.")

    if mv_data:
        top_mv = mv_data[0]
        lines.append(
            f"최근 컴백 MV 중 {top_mv['artist']}의 〈{top_mv['title']}〉이 "
            f"{fmt_views(top_mv['views'])} 조회수로 선두입니다."
        )

    lines.append("엔터산업 주요 동향을 아래에서 확인하세요.")
    return " ".join(lines)


# ────────────────────────────────────────────
# 7. HTML 빌더
# ────────────────────────────────────────────

def build_release_cards(recent: list[dict]) -> str:
    if not recent:
        return "<p class='empty'>최근 30일 내 신보 없음</p>"

    cards = []
    for r in recent:
        _, tag_cls  = TYPE_MAP.get(r["type"], (r["type"], "tag-pink"))
        genre_tags  = "".join(
            f'<span class="tag tag-gray">{g}</span>' for g in r["genres"]
        )
        track_info  = f"{r['total_tracks']}트랙" if r["total_tracks"] else ""
        meta_parts  = [p for p in [r["label"], track_info] if p]
        meta        = " · ".join(meta_parts)

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
        return "<p class='empty'>최근 컴백 MV 데이터 없음</p>"
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
    </div>
    <div class="mv-track"><div class="mv-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="mv-val">{fmt_views(mv['views'])}</div>
  </div>""")
    return "\n".join(rows)


def build_chart_rows(chart: list[dict]) -> str:
    if not chart:
        return "<p class='empty'>서클차트 데이터를 가져오지 못했습니다</p>"
    rows = []
    colors = BAR_COLORS
    max_score = len(chart)
    for item in chart:
        bar_pct = int((max_score - item["rank"] + 1) / max_score * 100)
        color   = colors[(item["rank"] - 1) % len(colors)]
        rank_badge = ""
        if item["rank"] == 1:
            rank_badge = '<span class="rank-badge rank-1">1위</span>'
        elif item["rank"] == 2:
            rank_badge = '<span class="rank-badge rank-2">2위</span>'
        elif item["rank"] == 3:
            rank_badge = '<span class="rank-badge rank-3">3위</span>'
        rows.append(f"""
  <div class="chart-row">
    <div class="chart-rank">{item['rank']}</div>
    <div class="chart-info">
      <div class="chart-title">{item['title']} {rank_badge}</div>
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
        date_str = f" · {a['date']}" if a["date"] else ""
        cards.append(f"""
  <div class="news-card">
    <div class="news-meta">네이버 뉴스{date_str}</div>
    <a class="news-title" href="{a['url']}" target="_blank">{a['title']}</a>
    <div class="news-summary">{a['summary']}</div>
  </div>""")
    return "\n".join(cards)


# ────────────────────────────────────────────
# 8. HTML 렌더링
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
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; margin-bottom:.6rem; }}
  .card-row {{ display:flex; gap:14px; align-items:flex-start; }}
  .card-icon {{ width:52px; height:52px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0; border:1px solid var(--border); }}
  .card-body {{ flex:1; min-width:0; }}
  .card-title {{ font-size:14px; font-weight:500; margin-bottom:3px; }}
  .card-source {{ font-size:11px; color:var(--text-muted); margin-bottom:2px; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .tag {{ font-size:11px; font-weight:500; padding:2px 9px; border-radius:99px; text-decoration:none; display:inline-block; }}
  .tag-purple {{ background:var(--purple-bg); color:var(--purple); }}
  .tag-blue   {{ background:var(--blue-bg);   color:var(--blue); }}
  .tag-pink   {{ background:var(--pink-bg);   color:var(--pink); }}
  .tag-teal   {{ background:var(--teal-bg);   color:var(--teal); }}
  .tag-amber  {{ background:var(--amber-bg);  color:var(--amber); }}
  .tag-gray   {{ background:#EDECE8; color:#5C5B57; }}
  .tag-spotify {{ background:#E3F7F1; color:#0D6B52; }}
  .mv-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .mv-row {{ display:flex; align-items:center; gap:10px; margin-bottom:10px; }}
  .mv-row:last-of-type {{ margin-bottom:0; }}
  .mv-rank {{ font-size:11px; font-weight:500; color:var(--text-muted); min-width:16px; text-align:right; }}
  .mv-name {{ font-size:13px; color:var(--text-secondary); flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .mv-track {{ width:100px; height:5px; background:var(--bg); border-radius:99px; overflow:hidden; flex-shrink:0; }}
  .mv-fill {{ height:100%; border-radius:99px; }}
  .mv-val {{ font-size:12px; font-weight:500; color:var(--text-primary); min-width:44px; text-align:right; }}
  .mv-note {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}
  .chart-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.25rem; }}
  .chart-row {{ display:flex; align-items:center; gap:12px; padding:.6rem 0; border-bottom:1px solid var(--border); }}
  .chart-row:last-child {{ border-bottom:none; }}
  .chart-rank {{ font-size:13px; font-weight:500; color:var(--text-muted); min-width:20px; text-align:center; }}
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
  .news-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1rem 1.25rem; margin-bottom:.6rem; }}
  .news-meta {{ font-size:10px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; color:var(--text-muted); margin-bottom:4px; }}
  .news-title {{ font-size:14px; font-weight:500; color:var(--text-primary); text-decoration:none; line-height:1.45; display:block; margin-bottom:5px; }}
  .news-title:hover {{ color:var(--purple); }}
  .news-summary {{ font-size:12px; color:var(--text-secondary); line-height:1.55; }}
  .footer {{ border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; font-size:12px; color:var(--text-muted); display:flex; align-items:center; justify-content:space-between; }}
  .footer a {{ color:var(--text-muted); text-decoration:none; }}
  .chart-source {{ font-size:11px; color:var(--text-muted); margin-top:10px; padding-top:10px; border-top:1px solid var(--border); }}
  @media(max-width:540px) {{
    .header h1 {{ font-size:26px; }}
    .mv-track {{ width:60px; }}
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
    <div class="section-label">신보 발매 소식 (최근 30일)</div>
    {release_cards}
  </div>

  <div class="section">
    <div class="section-label">최근 컴백 MV 조회수 — 공식 채널 기준</div>
    <div class="mv-card">
      {mv_rows}
      <div class="mv-note">* 최근 30일 내 발매 · 공식 YouTube 채널 영상 · 매일 오전 8시 업데이트</div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">서클차트 디지털 종합 주간 TOP 10</div>
    <div class="chart-card">
      {chart_rows}
      <div class="chart-source">* 서클차트(Circle Chart) 주간 디지털 종합 기준</div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">케이팝 뉴스</div>
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
# 9. 메인 실행
# ────────────────────────────────────────────

def main():
    print(f"[{TODAY}] K-pop Intelligence 생성 시작...")

    print("  → Spotify 신보 조회 중...")
    token  = get_spotify_token()
    recent = fetch_recent_releases(token)
    print(f"     최근 발매 {len(recent)}건")

    print("  → YouTube 공식 MV 조회수 수집 중...")
    mv_data = fetch_official_mv_views(recent)
    print(f"     MV {len(mv_data)}건")

    print("  → 서클차트 순위 수집 중...")
    chart = fetch_circle_chart(top_n=10)
    print(f"     차트 {len(chart)}위까지 수집")

    print("  → 네이버 뉴스 수집 중...")
    news = fetch_naver_kpop_news(max_items=8)
    print(f"     뉴스 {len(news)}건")

    print("  → HTML 렌더링 중...")
    html = render_html(recent, mv_data, chart, news)

    output_path = OUTPUT_DIR / f"{TODAY}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  → 완료: {output_path}")


if __name__ == "__main__":
    main()
