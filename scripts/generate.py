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
TIMEOUT = 8


# ── 기획사 채널 목록 ───────────────────────────
# handle: 유튜브 @핸들 또는 직접 channel_id
# YouTube API가 handle → channel_id 자동 변환
LABEL_CHANNELS = [
    {"name": "HYBE LABELS",             "handle": "HYBELABELS"},
    {"name": "SMTOWN",                   "handle": "SMTOWN"},
    {"name": "JYP Entertainment",        "handle": "JYPEntertainment"},
    {"name": "YG Entertainment",         "handle": "YGEntertainment"},
    {"name": "Starship Entertainment",   "handle": "STARSHIP_official"},
    {"name": "1theK",                    "handle": "1theK"},
    {"name": "Stone Music Entertainment","handle": "stonemusicent"},
    {"name": "CUBE Entertainment",       "channel_id": "UCritGVo7pLJLUS8wEu32vow"},
    {"name": "BELIFT LAB",               "channel_id": "UCg8ZzloDPTrOiGztK0C9txQ"},
    {"name": "THE BLACK LABEL",          "channel_id": "UCaMhpehN8xNWkVJB3ZQY0qQ"},
    {"name": "KQ Entertainment",         "handle": "KQENT"},
    {"name": "unknown_ch12",             "channel_id": "UCvEEeBssb4XxIfWWIB8IjMw"},
]

# 아티스트 → 소속 기획사 채널 매핑
ARTIST_LABEL_MAP = {
    "BTS":         "HYBE LABELS",
    "SEVENTEEN":   "HYBE LABELS",
    "ENHYPEN":     "HYBE LABELS",
    "TXT":         "HYBE LABELS",
    "LE SSERAFIM": "HYBE LABELS",
    "ILLIT":       "BELIFT LAB",
    "NewJeans":    "HYBE LABELS",
    "aespa":       "SMTOWN",
    "Red Velvet":  "SMTOWN",
    "RIIZE":       "SMTOWN",
    "TWICE":       "JYP Entertainment",
    "Stray Kids":  "JYP Entertainment",
    "NMIXX":       "JYP Entertainment",
    "BLACKPINK":   "YG Entertainment",
    "G-DRAGON":    "YG Entertainment",
    "IVE":         "Starship Entertainment",
    "Jennie":      "THE BLACK LABEL",
    "Rosé":        "THE BLACK LABEL",
    "(G)I-DLE":    "CUBE Entertainment",
    "ATEEZ":       "KQ Entertainment",
    "IU":          "1theK",
    "Lisa":        "1theK",
    "BINI":        "1theK",
}

# 고정 MV 목록 (video_id 직접 검증됨)
MV_LIST = [
    {"artist": "BTS",         "title": "Dynamite",       "video_id": "gdZLi9oWNZg", "channel": "HYBE LABELS"},
    {"artist": "BLACKPINK",   "title": "Pink Venom",      "video_id": "gQlMMD8auMs", "channel": "YG Entertainment"},
    {"artist": "aespa",       "title": "Supernova",       "video_id": "phuiiNCxRMg", "channel": "SMTOWN"},
    {"artist": "IVE",         "title": "Baddie",          "video_id": "Da4P2uT4mVc", "channel": "Starship Entertainment"},
    {"artist": "NewJeans",    "title": "Hype Boy",        "video_id": "11cta61wi0g", "channel": "HYBE LABELS"},
    {"artist": "SEVENTEEN",   "title": "MAESTRO",         "video_id": "tZj8ov1K7Zs", "channel": "HYBE LABELS"},
    {"artist": "Stray Kids",  "title": "MIROH",           "video_id": "Wv3vFpDFmjY", "channel": "JYP Entertainment"},
    {"artist": "LE SSERAFIM", "title": "ANTIFRAGILE",     "video_id": "pyf8cbqyfPs", "channel": "HYBE LABELS"},
    {"artist": "TWICE",       "title": "FANCY",           "video_id": "kOHB85vDuow", "channel": "JYP Entertainment"},
    {"artist": "(G)I-DLE",   "title": "Queencard",       "video_id": "wzmCGOcC1N0", "channel": "CUBE Entertainment"},
    {"artist": "ILLIT",       "title": "Magnetic",        "video_id": "JNTnhBmERQk", "channel": "HYBE LABELS"},
    {"artist": "Rosé",        "title": "APT.",            "video_id": "ArmDp-zijuc", "channel": "THE BLACK LABEL"},
    {"artist": "Jennie",      "title": "MANTRA",          "video_id": "ZMuGVCkJGCw", "channel": "THE BLACK LABEL"},
    {"artist": "RIIZE",       "title": "Impossible",      "video_id": "r2R3L-nKoUo", "channel": "SMTOWN"},
    {"artist": "G-DRAGON",    "title": "HOME SWEET HOME", "video_id": "6_d9BnJzQCY", "channel": "YG Entertainment"},
]

# 아티스트 Spotify 정보
ARTISTS = {
    "BLACKPINK":   {"spotify_id": "41MozSoPIsD1dJM0CLPjZF", "label": "YG 엔터테인먼트",      "genres": ["팝", "댄스팝"]},
    "IVE":         {"spotify_id": "6RHTUrRF63xao58xh9FXYJ", "label": "스타쉽 엔터테인먼트",   "genres": ["팝", "일렉트로팝"]},
    "NewJeans":    {"spotify_id": "2NZVRjbzIDfuSE6ESWJvvU", "label": "ADOR (HYBE)",        "genres": ["Y2K팝", "R&B"]},
    "SEVENTEEN":   {"spotify_id": "7nqOGox5dQiUgmxGUCjkjh", "label": "PLEDIS (HYBE)",      "genres": ["팝", "자체프로듀싱"]},
    "Stray Kids":  {"spotify_id": "2b4LTnUMBB34DWnFMKVEDP", "label": "JYP 엔터테인먼트",    "genres": ["하드팝", "자체프로듀싱"]},
    "aespa":       {"spotify_id": "2cnMpRsRX83sFl96xKXQ1",  "label": "SM 엔터테인먼트",     "genres": ["하이퍼팝", "세계관"]},
    "IU":          {"spotify_id": "3HqSZScBaE9dy3ySJpq0kk", "label": "EDAM 엔터테인먼트",   "genres": ["팝발라드", "인디팝"]},
    "Jennie":      {"spotify_id": "1Oa0bMld0A3u5N5eRMVLbk", "label": "OA (ODD ATELIER)",   "genres": ["팝", "힙합"]},
    "Rosé":        {"spotify_id": "2euSnPTJ3HgDhcfajnFmad", "label": "더블랙레이블",         "genres": ["인디팝", "팝록"]},
    "(G)I-DLE":   {"spotify_id": "2AfmfGFAFZaECNxqR2QKEZ", "label": "큐브 엔터테인먼트",   "genres": ["걸크러시", "자체프로듀싱"]},
    "Lisa":        {"spotify_id": "5DnBaQWjfBM69RQHX47aKr", "label": "LLOUD",               "genres": ["힙합", "댄스팝"]},
    "RIIZE":       {"spotify_id": "4PbOQFdGJJHu25UMZ1sTDR", "label": "SM 엔터테인먼트",     "genres": ["팝", "보이밴드"]},
    "ILLIT":       {"spotify_id": "3GjN0Vc5AkRBGAMuRXhaDI", "label": "BELIFT LAB (HYBE)",  "genres": ["버블팝", "큐트팝"]},
    "Red Velvet":  {"spotify_id": "1z4g3DjTBBZKhvAroFlhOM", "label": "SM 엔터테인먼트",     "genres": ["팝", "R&B"]},
    "G-DRAGON":    {"spotify_id": "5p5kkpXNUJsqBksBbdoWMB", "label": "갤럭시코퍼레이션",    "genres": ["힙합", "팝"]},
    "BTS":         {"spotify_id": "3Nrfpe0tUJi4K4DXYWgMUX", "label": "빅히트 뮤직 (HYBE)", "genres": ["팝", "힙합"]},
    "TWICE":       {"spotify_id": "7n2Ycct7Beij7Dj7meI4X0", "label": "JYP 엔터테인먼트",    "genres": ["팝", "댄스팝"]},
    "NMIXX":       {"spotify_id": "1tmxpdDbyKoCOXlSb7MGFU", "label": "JYP 엔터테인먼트",    "genres": ["믹스팝", "실험적"]},
    "ENHYPEN":     {"spotify_id": "0bktO5A1yBhMVTXXbQEjxW", "label": "BELIFT LAB (HYBE)",  "genres": ["팝", "다크팝"]},
    "TXT":         {"spotify_id": "4vGrte8FDu062Ntj0RsPiZ", "label": "빅히트 뮤직 (HYBE)", "genres": ["얼터너티브", "팝록"]},
    "ATEEZ":       {"spotify_id": "1Cd373x7Nf6QEHBHB7DNVG", "label": "KQ 엔터테인먼트",    "genres": ["퍼포먼스팝", "드라마틱"]},
    "LE SSERAFIM": {"spotify_id": "6HvZYsbFfjnjFrWF950C9d", "label": "SOURCE MUSIC (HYBE)", "genres": ["팝", "파워팝"]},
    "BINI":        {"spotify_id": "6MdRFpKXAMbBr88b1T3UM7", "label": "Star Music (PH)",    "genres": ["P-pop", "팝"]},
}

TYPE_MAP = {
    "album":       ("정규앨범", "tag-purple"),
    "single":      ("싱글",    "tag-teal"),
    "ep":          ("미니앨범", "tag-blue"),
    "compilation": ("컴필레이션","tag-amber"),
}
BAR_COLORS = ["#D4537E","#378ADD","#EF9F27","#1D9E75","#7F77DD",
               "#D85A30","#639922","#BA7517","#E24B4A","#5DCAA5"]

NEWS_CATEGORIES = {
    "컴백·신보":  {"keywords": ["컴백", "comeback", "신보", "발매", "release", "출시", "데뷔", "앨범"], "style": "cat-comeback"},
    "차트·성과":  {"keywords": ["차트", "순위", "1위", "빌보드", "조회수", "스트리밍", "기록", "chart", "views", "million"], "style": "cat-chart"},
    "글로벌":    {"keywords": ["투어", "콘서트", "페스티벌", "해외", "월드투어", "북미", "유럽", "tour", "concert", "global", "festival"], "style": "cat-global"},
    "브랜드":    {"keywords": ["브랜드", "앰버서더", "광고", "명품", "패션", "ambassador", "brand", "협찬", "모델", "루이비통", "샤넬"], "style": "cat-brand"},
    "비즈니스":  {"keywords": ["기획사", "주가", "실적", "계약", "AI", "버추얼", "산업", "매출", "인수", "hybe", "sm엔터", "jyp", "yg", "상장"], "style": "cat-biz"},
}


# ────────────────────────────────────────────
# 1. YouTube: @handle → channel_id 변환
# ────────────────────────────────────────────

def resolve_channel_ids(api_key: str) -> dict:
    """
    handle이 있는 채널은 YouTube API로 channel_id 조회.
    channel_id가 이미 있으면 그대로 사용.
    반환: {채널명: channel_id}
    """
    result = {}
    handles_to_resolve = []

    for ch in LABEL_CHANNELS:
        if "channel_id" in ch:
            result[ch["name"]] = ch["channel_id"]
        elif "handle" in ch:
            handles_to_resolve.append(ch)

    # YouTube API: forHandle 파라미터로 @handle → channel_id 변환
    for ch in handles_to_resolve:
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part":      "id",
                    "forHandle": ch["handle"],
                    "key":       api_key,
                },
                timeout=TIMEOUT,
            )
            items = r.json().get("items", [])
            if items:
                result[ch["name"]] = items[0]["id"]
                print(f"  채널 ID 확인: {ch['name']} → {items[0]['id']}")
            else:
                print(f"  채널 ID 조회 실패: {ch['name']} (@{ch['handle']})")
        except Exception as e:
            print(f"  채널 ID 오류 ({ch['name']}): {e}")

    return result


# ────────────────────────────────────────────
# 2. Spotify 토큰
# ────────────────────────────────────────────

def get_spotify_token() -> str:
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


# ────────────────────────────────────────────
# 3. Spotify: 최근 90일 신보
# ────────────────────────────────────────────

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
                params={"album_type": "album,single,ep", "limit": 5, "market": "KR"},
                timeout=TIMEOUT,
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
                        "genres":       info.get("genres", []),
                    })
        except Exception as e:
            print(f"  Spotify error ({artist_name}): {e}")

    recent.sort(key=lambda x: x["release_date"], reverse=True)
    return recent


# ────────────────────────────────────────────
# 4. YouTube: 최신 컴백 MV 검색 (기획사 공식 채널)
#    + 고정 MV 목록 조회수 일괄 수집
# ────────────────────────────────────────────

MV_TITLE_KEYWORDS = ["MV", "M/V", "MUSIC VIDEO", "뮤직비디오", "OFFICIAL VIDEO", "OFFICIAL MV"]

def fetch_recent_comeback_mvs(recent_releases: list[dict], channel_map: dict, api_key: str) -> list[dict]:
    """최근 발매 아티스트의 공식 MV를 기획사 채널에서 검색"""
    mv_results  = []
    seen_artists= set()

    for release in recent_releases:
        artist = release["artist"]
        if artist in seen_artists:
            continue
        seen_artists.add(artist)

        label_name = ARTIST_LABEL_MAP.get(artist)
        channel_id = channel_map.get(label_name) if label_name else None
        if not channel_id:
            continue

        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part":      "snippet",
                    "channelId": channel_id,
                    "q":         f"{artist} {release['title']}",
                    "type":      "video",
                    "order":     "date",
                    "maxResults": 5,
                    "key":       api_key,
                },
                timeout=TIMEOUT,
            )
            items = r.json().get("items", [])
            if not items:
                continue

            # MV/M/V 키워드 포함 영상 우선 선택
            video_id = None
            for item in items:
                vtitle = item["snippet"]["title"].upper()
                if any(kw in vtitle for kw in MV_TITLE_KEYWORDS):
                    video_id = item["id"]["videoId"]
                    break
            if not video_id:
                video_id = items[0]["id"]["videoId"]

            # 조회수
            stats_r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": video_id, "key": api_key},
                timeout=TIMEOUT,
            )
            stats_items = stats_r.json().get("items", [])
            if not stats_items:
                continue

            views = int(stats_items[0]["statistics"].get("viewCount", 0))
            if views > 0:
                mv_results.append({
                    "artist":       artist,
                    "title":        release["title"],
                    "video_id":     video_id,
                    "views":        views,
                    "channel":      label_name or "",
                    "release_date": release["release_date"],
                    "is_recent":    True,
                })
        except Exception as e:
            print(f"  YouTube search error ({artist}): {e}")

    return mv_results


def fetch_fixed_mv_views(api_key: str) -> list[dict]:
    """고정 MV 목록 조회수 일괄 수집 (API 1회 호출)"""
    video_ids = ",".join(mv["video_id"] for mv in MV_LIST)
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": video_ids, "key": api_key},
            timeout=TIMEOUT,
        )
        stats = {
            item["id"]: int(item["statistics"].get("viewCount", 0))
            for item in r.json().get("items", [])
        }
    except Exception as e:
        print(f"  YouTube fixed MV error: {e}")
        stats = {}

    return [{**mv, "views": stats.get(mv["video_id"], 0), "is_recent": False} for mv in MV_LIST]


def build_mv_data(recent_releases: list[dict], channel_map: dict, api_key: str) -> list[dict]:
    """
    최근 컴백 MV + 고정 MV 합쳐서 조회수 순 정렬.
    최근 컴백 MV가 있으면 고정 목록 중복 아티스트 제거.
    """
    recent_mvs = fetch_recent_comeback_mvs(recent_releases, channel_map, api_key)
    fixed_mvs  = fetch_fixed_mv_views(api_key)

    # 최근 MV에 있는 아티스트는 고정 목록에서 제외
    recent_artists = {mv["artist"] for mv in recent_mvs}
    filtered_fixed = [mv for mv in fixed_mvs if mv["artist"] not in recent_artists]

    combined = recent_mvs + filtered_fixed
    combined.sort(key=lambda x: x["views"], reverse=True)
    return combined[:15]


def fmt_views(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.1f}M"
    if n >= 1_000:         return f"{n/1_000:.0f}K"
    return str(n)


# ────────────────────────────────────────────
# 5. 구글 뉴스 RSS: 5가지 카테고리 뉴스
# ────────────────────────────────────────────

def classify_category(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cat, info in NEWS_CATEGORIES.items():
        score = sum(1 for kw in info["keywords"] if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "컴백·신보"


def fetch_kpop_news(max_items: int = 10) -> list[dict]:
    if feedparser is None:
        return []

    QUERIES = [
        "케이팝 컴백 신보 발매",
        "K-pop 차트 조회수 순위",
        "케이팝 콘서트 투어 해외",
        "아이돌 브랜드 앰버서더 광고",
        "엔터테인먼트 기획사 K-pop 비즈니스",
    ]
    seen, articles = set(), []

    for query in QUERIES:
        if len(articles) >= max_items:
            break
        try:
            url  = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if len(articles) >= max_items:
                    break
                title    = entry.get("title", "").strip()
                headline, source = (title.rsplit(" - ", 1) if " - " in title else (title, ""))
                link     = entry.get("link", "")
                desc     = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
                summary  = desc[:110] + "..." if len(desc) > 110 else desc
                date     = entry.get("published", "")[:10]
                cat      = classify_category(headline + " " + summary)

                if headline in seen or not headline:
                    continue
                seen.add(headline)
                articles.append({
                    "title": headline, "source": source,
                    "url": link, "summary": summary,
                    "date": date, "category": cat,
                })
        except Exception as e:
            print(f"  Google News RSS error ({query}): {e}")

    return articles[:max_items]


# ────────────────────────────────────────────
# 6. 신보-뉴스 연결
# ────────────────────────────────────────────

def link_news_to_releases(recent: list[dict], news: list[dict]) -> dict:
    linked = {}
    for release in recent:
        artist  = release["artist"]
        matched = [a for a in news if artist.lower() in (a["title"] + a["summary"]).lower()]
        if matched:
            linked[artist] = matched[:2]
    return linked


# ────────────────────────────────────────────
# 7. 서문
# ────────────────────────────────────────────

def build_intro(recent, mv_data, news) -> str:
    lines = []
    if recent:
        names  = ", ".join(f"{r['artist']} 《{r['title']}》" for r in recent[:2])
        suffix = f" 등 총 {len(recent)}건" if len(recent) > 2 else ""
        lines.append(f"최근 90일간 {names}{suffix}이 발매됐습니다.")
    else:
        lines.append("최근 90일간 등록된 아티스트의 새로운 발매 소식은 없습니다.")
    top_mv = next((mv for mv in mv_data if mv["views"] > 0), None)
    if top_mv:
        lines.append(f"MV 조회수는 {top_mv['artist']}의 〈{top_mv['title']}〉이 {fmt_views(top_mv['views'])}으로 선두입니다.")
    if news:
        cat_counts = {}
        for a in news:
            cat_counts[a["category"]] = cat_counts.get(a["category"], 0) + 1
        top_cat = max(cat_counts, key=cat_counts.get)
        lines.append(f"이번 주 뉴스는 '{top_cat}' 관련 소식이 가장 많습니다.")
    lines.append("엔터산업 주요 동향을 아래에서 확인하세요.")
    return " ".join(lines)


# ────────────────────────────────────────────
# 8. HTML 빌더
# ────────────────────────────────────────────

def build_release_cards(recent: list[dict], news_linked: dict) -> str:
    if not recent:
        return "<p class='empty'>최근 90일 내 신보 없음</p>"
    cards = []
    for r in recent:
        _, tag_cls = TYPE_MAP.get(r["type"], (r["type"], "tag-pink"))
        track_info = f"{r['total_tracks']}트랙" if r["total_tracks"] else ""
        meta = " · ".join(p for p in [r["label"], track_info] if p)
        genre_tags = "".join(f'<span class="tag tag-gray">{g}</span>' for g in r.get("genres", []))

        linked_html = ""
        if r["artist"] in news_linked:
            items = "".join(
                f'<a class="linked-news" href="{n["url"]}" target="_blank">'
                f'<span class="linked-cat {NEWS_CATEGORIES[n["category"]]["style"]}">{n["category"]}</span>'
                f'<span class="linked-title">{n["title"]}</span>'
                f'</a>'
                for n in news_linked[r["artist"]]
            )
            linked_html = f'<div class="linked-news-wrap">{items}</div>'

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
        {linked_html}
      </div>
    </div>
  </div>""")
    return "\n".join(cards)


def build_mv_rows(mv_data: list[dict]) -> str:
    if not mv_data:
        return "<p class='empty'>MV 데이터 없음</p>"
    max_v = max((mv["views"] for mv in mv_data), default=1) or 1
    rows  = []
    for i, mv in enumerate(mv_data):
        pct    = int(mv["views"] / max_v * 100)
        color  = BAR_COLORS[i % len(BAR_COLORS)]
        yt_url = f"https://www.youtube.com/watch?v={mv['video_id']}"
        recent_badge = '<span class="recent-badge">최신</span>' if mv.get("is_recent") else ""
        rows.append(f"""
  <div class="mv-row">
    <div class="mv-rank">{i+1}</div>
    <div class="mv-name">
      <a href="{yt_url}" target="_blank" style="color:inherit;text-decoration:none;">
        {mv['artist']} — {mv['title']} {recent_badge}
      </a>
      <span class="mv-ch">via {mv['channel']}</span>
    </div>
    <div class="mv-track"><div class="mv-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="mv-val">{fmt_views(mv['views'])}</div>
  </div>""")
    return "\n".join(rows)


def build_news_cards(articles: list[dict]) -> str:
    if not articles:
        return "<p class='empty'>뉴스를 가져오지 못했습니다</p>"
    cards = []
    for a in articles:
        cat      = a.get("category", "컴백·신보")
        cat_info = NEWS_CATEGORIES.get(cat, {"style": "cat-comeback"})
        source   = a["source"] if a["source"] else "Google 뉴스"
        date_str = f" · {a['date']}" if a["date"] else ""
        cards.append(f"""
  <a class="news-card" href="{a['url']}" target="_blank">
    <div class="news-top">
      <span class="news-cat {cat_info['style']}">{cat}</span>
      <span class="news-meta">{source}{date_str}</span>
    </div>
    <div class="news-title">{a['title']}</div>
    <div class="news-summary">{a['summary']}</div>
    <span class="ext-arrow">원문 보기 →</span>
  </a>""")
    return "\n".join(cards)


# ────────────────────────────────────────────
# 9. HTML 렌더링
# ────────────────────────────────────────────

def render_html(recent, mv_data, news) -> str:
    news_linked   = link_news_to_releases(recent, news)
    intro         = build_intro(recent, mv_data, news)
    release_cards = build_release_cards(recent, news_linked)
    mv_rows       = build_mv_rows(mv_data)
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
  .linked-news-wrap {{ margin-top:10px; padding-top:10px; border-top:1px dashed var(--border-strong); display:flex; flex-direction:column; gap:5px; }}
  .linked-news {{ display:flex; align-items:center; gap:7px; text-decoration:none; padding:5px 8px; border-radius:8px; background:var(--bg); transition:background .1s; }}
  .linked-news:hover {{ background:#EDECE8; }}
  .linked-cat {{ font-size:10px; font-weight:500; padding:1px 7px; border-radius:99px; white-space:nowrap; flex-shrink:0; }}
  .linked-title {{ font-size:12px; color:var(--text-secondary); line-height:1.4; }}
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
  .recent-badge {{ font-size:9px; font-weight:500; padding:1px 5px; background:var(--pink-bg); color:var(--pink); border-radius:99px; vertical-align:middle; margin-left:4px; }}
  .news-card {{ display:block; text-decoration:none; background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:1rem 1.25rem; margin-bottom:.6rem; transition:border-color .1s; }}
  .news-card:hover {{ border-color:rgba(0,0,0,.2); }}
  .news-top {{ display:flex; align-items:center; gap:8px; margin-bottom:6px; }}
  .news-cat {{ font-size:10px; font-weight:500; padding:2px 8px; border-radius:99px; white-space:nowrap; }}
  .news-meta {{ font-size:10px; color:var(--text-muted); margin-left:auto; white-space:nowrap; }}
  .news-title {{ font-size:14px; font-weight:500; color:var(--text-primary); line-height:1.45; margin-bottom:4px; }}
  .news-summary {{ font-size:12px; color:var(--text-secondary); line-height:1.55; margin-bottom:6px; }}
  .ext-arrow {{ font-size:11px; color:var(--text-muted); font-weight:500; }}
  .cat-comeback {{ background:#FBEAF0; color:#72243E; }}
  .cat-chart    {{ background:#FDF0D8; color:#633806; }}
  .cat-global   {{ background:#E8F0FA; color:#0C447C; }}
  .cat-brand    {{ background:#EEEDFC; color:#3C3489; }}
  .cat-biz      {{ background:#E3F7F1; color:#085041; }}
  .footer {{ border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; font-size:12px; color:var(--text-muted); display:flex; align-items:center; justify-content:space-between; }}
  .footer a {{ color:var(--text-muted); text-decoration:none; }}
  @media(max-width:540px) {{
    .header h1 {{ font-size:26px; }}
    .mv-track {{ width:50px; }}
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
    <div class="section-label">주요 MV 조회수 — 기획사 공식 채널 기준</div>
    <div class="mv-card">
      {mv_rows}
      <div class="mv-note">* 기획사 공식 채널 MV 및 M/V 기준 · 유튜브 누적 조회수 · 매일 오전 8시 업데이트</div>
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
# 10. 메인 실행
# ────────────────────────────────────────────

def main():
    print(f"[{TODAY}] K-pop Intelligence 생성 시작...")
    api_key = os.environ["YOUTUBE_API_KEY"]

    print("  → 기획사 YouTube 채널 ID 확인 중...")
    channel_map = resolve_channel_ids(api_key)
    print(f"     {len(channel_map)}개 채널 확인 완료")

    print("  → Spotify 신보 조회 중...")
    token  = get_spotify_token()
    recent = fetch_recent_releases(token, days=90)
    print(f"     최근 발매 {len(recent)}건")

    print("  → YouTube MV 조회수 수집 중...")
    mv_data = build_mv_data(recent, channel_map, api_key)
    print(f"     MV {len(mv_data)}건 (최신 컴백 포함)")

    print("  → 케이팝 뉴스 수집 중...")
    news = fetch_kpop_news(max_items=10)
    print(f"     뉴스 {len(news)}건")

    print("  → HTML 렌더링 중...")
    html = render_html(recent, mv_data, news)

    output_path = OUTPUT_DIR / f"{TODAY}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  → 완료: {output_path}")


if __name__ == "__main__":
    main()
