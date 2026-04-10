"""
K-pop 데일리 브리핑 생성기
매일 GitHub Actions에서 자동 실행됩니다.

필요한 환경변수 (GitHub Secrets):
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  YOUTUBE_API_KEY
"""

import os, re, datetime, requests
from pathlib import Path
from urllib.parse import quote

try:
    import feedparser
except ImportError:
    feedparser = None

# ─────────────────────────────────────────────
# 0. 기본 설정
# ─────────────────────────────────────────────

TODAY    = datetime.date.today().isoformat()          # 2026-04-10
DAY_KO   = ["월","화","수","목","금","토","일"][datetime.date.today().weekday()]
DAY_EN   = datetime.date.today().strftime("%b %d").upper()  # APR 10
YEAR_EN  = datetime.date.today().strftime("%Y")
OUT_DIR  = Path("newsletters")
OUT_DIR.mkdir(exist_ok=True)
TO       = 8   # API 타임아웃 (초)

# ─────────────────────────────────────────────
# 1. 컴백 일정 설정
#    Spotify API로 신보 감지 + 수동 보완
# ─────────────────────────────────────────────

# Spotify 아티스트 목록
ARTISTS = {
    "aespa":       {"sid": "2cnMpRsRX83sFl96xKXQ1",  "label": "SM 엔터테인먼트",      "type_label": "정규앨범"},
    "SEVENTEEN":   {"sid": "7nqOGox5dQiUgmxGUCjkjh", "label": "PLEDIS (HYBE)",       "type_label": "미니앨범"},
    "ILLIT":       {"sid": "3GjN0Vc5AkRBGAMuRXhaDI",  "label": "BELIFT LAB (HYBE)",  "type_label": "미니앨범"},
    "NewJeans":    {"sid": "2NZVRjbzIDfuSE6ESWJvvU",  "label": "ADOR (HYBE)",         "type_label": "미니앨범"},
    "Stray Kids":  {"sid": "2b4LTnUMBB34DWnFMKVEDP",  "label": "JYP 엔터테인먼트",   "type_label": "정규앨범"},
    "TWICE":       {"sid": "7n2Ycct7Beij7Dj7meI4X0",  "label": "JYP 엔터테인먼트",   "type_label": "미니앨범"},
    "NMIXX":       {"sid": "1tmxpdDbyKoCOXlSb7MGFU",  "label": "JYP 엔터테인먼트",   "type_label": "미니앨범"},
    "IVE":         {"sid": "6RHTUrRF63xao58xh9FXYJ",  "label": "스타쉽 엔터테인먼트", "type_label": "미니앨범"},
    "BLACKPINK":   {"sid": "41MozSoPIsD1dJM0CLPjZF",  "label": "YG 엔터테인먼트",    "type_label": "정규앨범"},
    "BTS":         {"sid": "3Nrfpe0tUJi4K4DXYWgMUX",  "label": "빅히트 뮤직 (HYBE)", "type_label": "정규앨범"},
    "ENHYPEN":     {"sid": "0bktO5A1yBhMVTXXbQEjxW",  "label": "BELIFT LAB (HYBE)",  "type_label": "미니앨범"},
    "TXT":         {"sid": "4vGrte8FDu062Ntj0RsPiZ",  "label": "빅히트 뮤직 (HYBE)", "type_label": "미니앨범"},
    "ATEEZ":       {"sid": "1Cd373x7Nf6QEHBHB7DNVG",  "label": "KQ 엔터테인먼트",    "type_label": "정규앨범"},
    "LE SSERAFIM": {"sid": "6HvZYsbFfjnjFrWF950C9d",  "label": "SOURCE MUSIC (HYBE)", "type_label": "미니앨범"},
    "Jennie":      {"sid": "1Oa0bMld0A3u5N5eRMVLbk",  "label": "OA (ODD ATELIER)",   "type_label": "싱글"},
    "Rosé":        {"sid": "2euSnPTJ3HgDhcfajnFmad",  "label": "더블랙레이블",         "type_label": "싱글"},
    "(G)I-DLE":   {"sid": "2AfmfGFAFZaECNxqR2QKEZ",  "label": "큐브 엔터테인먼트",   "type_label": "정규앨범"},
    "RIIZE":       {"sid": "4PbOQFdGJJHu25UMZ1sTDR",  "label": "SM 엔터테인먼트",     "type_label": "미니앨범"},
    "BINI":        {"sid": "6MdRFpKXAMbBr88b1T3UM7",  "label": "Star Music (PH)",    "type_label": "EP"},
}

# 앨범 타입 → 한국어 & CSS 클래스
ALBUM_TYPE = {
    "album":       ("정규앨범", "type-album"),
    "single":      ("싱글",    "type-single"),
    "ep":          ("EP",      "type-ep"),
    "compilation": ("컴필",    "type-ep"),
}

def get_spotify_token():
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
        timeout=TO,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def fetch_comebacks(token: str, days=90) -> list[dict]:
    """최근 90일 발매 + 오늘 이후 예정 발매 모두 수집"""
    headers = {"Authorization": f"Bearer {token}"}
    today   = datetime.date.today()
    cutoff  = today - datetime.timedelta(days=days)
    items, seen = [], set()

    for name, info in ARTISTS.items():
        try:
            r = requests.get(
                f"https://api.spotify.com/v1/artists/{info['sid']}/albums",
                headers=headers,
                params={"album_type": "album,single,ep", "limit": 5, "market": "KR"},
                timeout=TO,
            )
            for album in r.json().get("items", []):
                raw = album.get("release_date", "")
                try:
                    rel = datetime.date.fromisoformat(raw[:10])
                except ValueError:
                    continue
                key = (name, album["name"])
                if key in seen:
                    continue
                seen.add(key)
                # 90일 내 발매 또는 미래 발매 모두 포함
                if rel >= cutoff:
                    raw_type = album["album_type"]
                    type_ko, type_cls = ALBUM_TYPE.get(raw_type, ("싱글", "type-single"))
                    delta = (rel - today).days
                    if delta < 0:
                        dday_label, dday_cls = "완료", "done"
                    elif delta == 0:
                        dday_label, dday_cls = "오늘", "today"
                    elif delta <= 7:
                        dday_label, dday_cls = f"D-{delta}", "soon"
                    else:
                        dday_label, dday_cls = f"D-{delta}", "future"
                    items.append({
                        "artist":      name,
                        "album":       album["name"],
                        "label":       info["label"],
                        "type_ko":     type_ko,
                        "type_cls":    type_cls,
                        "date":        raw[:10],
                        "delta":       delta,
                        "dday_label":  dday_label,
                        "dday_cls":    dday_cls,
                        "spotify_url": album["external_urls"]["spotify"],
                    })
        except Exception as e:
            print(f"  Spotify error ({name}): {e}")

    # 발매일 오름차순 (완료는 최근 것부터, 예정은 가까운 것부터)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items

# ─────────────────────────────────────────────
# 2. YouTube MV 조회수
#    • 발매 1주 이내 신규 MV: 기획사 채널 검색
#    • 고정 MV 목록: video_id 직접 지정
# ─────────────────────────────────────────────

# @handle → channel_id 매핑 (YouTube API로 자동 해결)
LABEL_HANDLES = [
    {"name": "HYBE LABELS",            "handle": "HYBELABELS"},
    {"name": "SMTOWN",                  "handle": "SMTOWN"},
    {"name": "JYP Entertainment",       "handle": "JYPEntertainment"},
    {"name": "YG Entertainment",        "handle": "YGEntertainment"},
    {"name": "Starship Entertainment",  "handle": "STARSHIP_official"},
    {"name": "1theK",                   "handle": "1theK"},
    {"name": "Stone Music",             "handle": "stonemusicent"},
    {"name": "CUBE Entertainment",      "channel_id": "UCritGVo7pLJLUS8wEu32vow"},
    {"name": "BELIFT LAB",              "channel_id": "UCg8ZzloDPTrOiGztK0C9txQ"},
    {"name": "THE BLACK LABEL",         "channel_id": "UCaMhpehN8xNWkVJB3ZQY0qQ"},
    {"name": "KQ Entertainment",        "handle": "KQENT"},
]

# 아티스트 → 기획사 채널 매핑
ARTIST_CHANNEL = {
    "BTS": "HYBE LABELS", "SEVENTEEN": "HYBE LABELS", "ENHYPEN": "HYBE LABELS",
    "TXT": "HYBE LABELS",  "LE SSERAFIM": "HYBE LABELS", "NewJeans": "HYBE LABELS",
    "ILLIT": "BELIFT LAB",
    "aespa": "SMTOWN", "Red Velvet": "SMTOWN", "RIIZE": "SMTOWN",
    "TWICE": "JYP Entertainment", "Stray Kids": "JYP Entertainment", "NMIXX": "JYP Entertainment",
    "BLACKPINK": "YG Entertainment", "G-DRAGON": "YG Entertainment",
    "IVE": "Starship Entertainment",
    "Jennie": "THE BLACK LABEL", "Rosé": "THE BLACK LABEL",
    "(G)I-DLE": "CUBE Entertainment",
    "ATEEZ": "KQ Entertainment",
    "IU": "1theK", "Lisa": "1theK", "BINI": "1theK",
}

# 검증된 고정 MV 목록 (항상 표시)
FIXED_MVS = [
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

MV_KW = ["MV", "M/V", "MUSIC VIDEO", "뮤직비디오", "OFFICIAL VIDEO", "OFFICIAL MV"]

def resolve_channels(api_key: str) -> dict:
    """handle → channel_id 변환. 이미 channel_id 있으면 그대로."""
    ch_map = {}
    for ch in LABEL_HANDLES:
        if "channel_id" in ch:
            ch_map[ch["name"]] = ch["channel_id"]
        else:
            try:
                r = requests.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "id", "forHandle": ch["handle"], "key": api_key},
                    timeout=TO,
                )
                items = r.json().get("items", [])
                if items:
                    ch_map[ch["name"]] = items[0]["id"]
                    print(f"  채널 확인: {ch['name']} → {items[0]['id']}")
            except Exception as e:
                print(f"  채널 오류 ({ch['name']}): {e}")
    return ch_map

def search_new_mv(artist: str, album_title: str, channel_id: str, api_key: str) -> dict | None:
    """기획사 공식 채널에서 발매 1주 이내 MV 검색"""
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet", "channelId": channel_id,
                "q": f"{artist} {album_title}",
                "type": "video", "order": "date", "maxResults": 5,
                "key": api_key,
            },
            timeout=TO,
        )
        items = r.json().get("items", [])
        if not items:
            return None
        # MV 키워드 포함 우선
        vid = None
        for item in items:
            if any(kw in item["snippet"]["title"].upper() for kw in MV_KW):
                vid = item["id"]["videoId"]
                break
        if not vid:
            vid = items[0]["id"]["videoId"]
        # 조회수
        sr = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": vid, "key": api_key},
            timeout=TO,
        )
        si = sr.json().get("items", [])
        if not si:
            return None
        views = int(si[0]["statistics"].get("viewCount", 0))
        if views == 0:
            return None
        return {"artist": artist, "title": album_title, "video_id": vid,
                "views": views, "channel": "", "is_new": True}
    except Exception as e:
        print(f"  YouTube search ({artist}): {e}")
        return None

def fetch_fixed_views(api_key: str) -> list[dict]:
    ids = ",".join(m["video_id"] for m in FIXED_MVS)
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": ids, "key": api_key},
            timeout=TO,
        )
        stats = {i["id"]: int(i["statistics"].get("viewCount", 0))
                 for i in r.json().get("items", [])}
    except Exception as e:
        print(f"  YouTube fixed: {e}")
        stats = {}
    return [{**m, "views": stats.get(m["video_id"], 0), "is_new": False} for m in FIXED_MVS]

def get_mv_list(comebacks: list[dict], ch_map: dict, api_key: str) -> list[dict]:
    """발매 1주 이내 신규 MV + 고정 목록 합산, 조회수 순 정렬"""
    today = datetime.date.today()
    new_mvs, seen = [], set()

    for cb in comebacks:
        if cb["delta"] < -7 or cb["delta"] > 0:
            continue   # 1주 이내 발매만
        artist = cb["artist"]
        if artist in seen:
            continue
        seen.add(artist)
        ch_name = ARTIST_CHANNEL.get(artist)
        ch_id   = ch_map.get(ch_name) if ch_name else None
        if not ch_id:
            continue
        mv = search_new_mv(artist, cb["album"], ch_id, api_key)
        if mv:
            mv["channel"] = ch_name or ""
            new_mvs.append(mv)

    fixed = fetch_fixed_views(api_key)
    new_artists = {m["artist"] for m in new_mvs}
    combined = new_mvs + [m for m in fixed if m["artist"] not in new_artists]
    combined.sort(key=lambda x: x["views"], reverse=True)
    return combined[:15]

def fmt_views(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1e9:.2f}B"
    if n >= 1_000_000:     return f"{n/1e6:.1f}M"
    if n >= 1_000:         return f"{n/1e3:.0f}K"
    return str(n)

# ─────────────────────────────────────────────
# 3. 구글 뉴스 RSS: 뉴스 클리핑
# ─────────────────────────────────────────────

# 7가지 카테고리 정의
CATEGORIES = {
    "컴백/신보":        {"kw": ["컴백","comeback","신보","발매","release","데뷔","앨범","출시"],       "cls": "tag-comeback"},
    "차트성과":         {"kw": ["차트","순위","1위","빌보드","조회수","스트리밍","기록","million"],    "cls": "tag-chart"},
    "글로벌":          {"kw": ["해외","글로벌","global","빌보드","북미","유럽","일본","아시아"],       "cls": "tag-global"},
    "아티스트 브랜드":  {"kw": ["브랜드","앰버서더","광고","명품","패션","ambassador","협찬","모델"],  "cls": "tag-brand"},
    "콘서트":          {"kw": ["콘서트","투어","공연","concert","tour","매진","페스티벌"],            "cls": "tag-concert"},
    "엔터 비즈니스":   {"kw": ["기획사","주가","실적","매출","계약","경영","인수","상장","hybe","sm","jyp","yg"], "cls": "tag-biz"},
    "엔터 기술":       {"kw": ["AI","인공지능","버추얼","virtual","기술","tech","플랫폼","메타버스"], "cls": "tag-tech"},
}

def classify(text: str) -> list[str]:
    t = text.lower()
    found = []
    for cat, info in CATEGORIES.items():
        if any(kw.lower() in t for kw in info["kw"]):
            found.append(cat)
    return found[:2] if found else ["컴백/신보"]

def fetch_news(max_n=10) -> list[dict]:
    """
    네이버 뉴스 RSS로 케이팝/엔터 관련 뉴스 수집.
    네이버 뉴스 검색 RSS: https://news.naver.com/rss/search?query=검색어&type=0
    """
    if not feedparser:
        return []

    # 네이버 뉴스 검색 RSS — 카테고리별 쿼리
    NAVER_QUERIES = [
        "케이팝 컴백",
        "케이팝 신보 발매",
        "아이돌 투어 콘서트",
        "케이팝 차트 순위",
        "아이돌 브랜드 앰버서더",
        "엔터테인먼트 기획사 실적",
        "K팝 AI 버추얼",
    ]

    seen, arts = set(), []

    for q in NAVER_QUERIES:
        if len(arts) >= max_n:
            break
        try:
            encoded = quote(q)
            url  = f"https://news.naver.com/rss/search?query={encoded}&type=0"
            feed = feedparser.parse(url)

            # RSS가 비어있으면 네이버 검색 RSS 시도
            if not feed.entries:
                url  = f"https://search.naver.com/rss?query={encoded}&where=news"
                feed = feedparser.parse(url)

            for e in feed.entries[:3]:
                if len(arts) >= max_n:
                    break

                title = re.sub(r"<[^>]+>", "", e.get("title", "")).strip()
                url_a = e.get("link", e.get("url", ""))
                date  = e.get("published", e.get("pubDate", ""))[:10]

                # 출처 추출
                source = ""
                if hasattr(e, "source") and hasattr(e.source, "title"):
                    source = e.source.title
                elif e.get("author"):
                    source = e.get("author")

                desc  = re.sub(r"<[^>]+>", "", e.get("description", e.get("summary", ""))).strip()
                cats  = classify(title + " " + desc)

                if not title or title in seen:
                    continue
                seen.add(title)
                arts.append({
                    "title":  title,
                    "source": source,
                    "url":    url_a,
                    "date":   date,
                    "cats":   cats,
                })
        except Exception as ex:
            print(f"  네이버 RSS ({q}): {ex}")

    return arts[:max_n]

# ─────────────────────────────────────────────
# 4. HTML 렌더링
# ─────────────────────────────────────────────

BAR_COLORS = ["#C8102E","#1A3A6B","#444","#666","#888",
              "#C8102E","#1A3A6B","#444","#666","#888",
              "#C8102E","#1A3A6B","#444","#666","#888"]

def render(comebacks, mvs, news) -> str:
    # ── 컴백 행
    cb_rows = ""
    for cb in comebacks[:10]:
        cb_rows += f"""
      <div class="comeback-item">
        <div class="cb-dday {cb['dday_cls']}">{cb['dday_label']}</div>
        <div class="cb-info">
          <div class="cb-artist">{cb['artist']}</div>
          <div class="cb-album">《{cb['album']}》</div>
        </div>
        <div class="cb-meta">
          <div class="cb-label">{cb['label']}</div>
          <span class="cb-type {cb['type_cls']}">{cb['type_ko']}</span>
        </div>
      </div>"""
    if not cb_rows:
        cb_rows = "<div style='padding:1rem;color:#999;font-size:13px;'>수집된 발매 일정이 없습니다</div>"

    # ── MV 행
    max_v = max((m["views"] for m in mvs), default=1) or 1
    mv_rows = ""
    for i, mv in enumerate(mvs):
        pct   = int(mv["views"] / max_v * 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        url   = f"https://www.youtube.com/watch?v={mv['video_id']}"
        new_b = '<span class="mv-new">NEW</span>' if mv.get("is_new") else ""
        mv_rows += f"""
      <div class="mv-row">
        <div class="mv-rank">{i+1}</div>
        <div class="mv-info">
          <a class="mv-title" href="{url}" target="_blank">
            {mv['artist']} — {mv['title']} {new_b}
          </a>
          <div class="mv-ch">via {mv['channel']}</div>
        </div>
        <div class="mv-bar-wrap">
          <div class="mv-bar-track">
            <div class="mv-bar-fill" style="width:{pct}%;background:{color};"></div>
          </div>
          <div class="mv-views">{fmt_views(mv['views'])}</div>
        </div>
      </div>"""

    # ── 뉴스 행
    news_rows = ""
    for i, a in enumerate(news, 1):
        tags = "".join(
            f'<span class="tag {CATEGORIES[c]["cls"]}">{c}</span>'
            for c in a["cats"]
        )
        news_rows += f"""
      <a class="news-card" href="{a['url']}" target="_blank">
        <div class="news-num">{i:02d}</div>
        <div class="news-body">
          <div class="news-tags">{tags}</div>
          <div class="news-headline">{a['title']}</div>
          <div class="news-meta-row">
            <span class="news-source">{a['source']}</span>
            <span class="news-arrow">원문 →</span>
          </div>
        </div>
      </a>"""
    if not news_rows:
        news_rows = "<div style='padding:1rem;color:#999;font-size:13px;'>뉴스를 가져오지 못했습니다</div>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>K-POP 데일리 브리핑 · {TODAY}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#0E0E0E; --ink2:#3A3A3A; --ink3:#7A7A7A;
  --paper:#F9F7F4; --surface:#FFFFFF;
  --rule:rgba(0,0,0,0.1); --rule2:rgba(0,0,0,0.06);
  --accent:#C8102E; --accent2:#1A3A6B;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Noto Sans KR',sans-serif;background:var(--paper);color:var(--ink);font-size:14px;line-height:1.7;}}
.page{{max-width:760px;margin:0 auto;padding:0 1.5rem 5rem;}}
.masthead{{padding:2.5rem 0 1.5rem;border-bottom:2px solid var(--ink);margin-bottom:2rem;display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;}}
.brand{{font-family:'Playfair Display',serif;font-size:11px;letter-spacing:0.28em;text-transform:uppercase;color:var(--ink3);margin-bottom:0.4rem;}}
.masthead h1{{font-family:'Playfair Display',serif;font-size:clamp(26px,5vw,42px);font-weight:700;line-height:1.05;letter-spacing:-0.02em;}}
.masthead h1 em{{font-style:italic;color:var(--accent);}}
.masthead-right{{text-align:right;flex-shrink:0;}}
.date-block{{font-family:'Playfair Display',serif;font-size:11px;letter-spacing:0.14em;color:var(--ink3);line-height:1.8;}}
.date-block strong{{display:block;font-size:22px;font-weight:400;letter-spacing:-0.01em;color:var(--ink);}}
.section{{margin-bottom:2.5rem;}}
.section-head{{display:flex;align-items:center;gap:10px;margin-bottom:1rem;padding-bottom:0.6rem;border-bottom:1px solid var(--rule);}}
.section-num{{font-family:'Playfair Display',serif;font-size:10px;color:var(--accent);letter-spacing:0.1em;}}
.section-title{{font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink2);}}
.comeback-list{{background:var(--surface);border:1px solid var(--rule);border-radius:3px;overflow:hidden;}}
.comeback-item{{display:flex;align-items:center;gap:14px;padding:0.85rem 1.1rem;border-bottom:1px solid var(--rule2);transition:background 0.1s;}}
.comeback-item:last-child{{border-bottom:none;}}
.comeback-item:hover{{background:#F5F3F0;}}
.cb-dday{{font-family:'Playfair Display',serif;font-size:11px;font-weight:700;min-width:48px;text-align:center;color:#fff;padding:3px 6px;border-radius:2px;flex-shrink:0;}}
.cb-dday.done{{background:var(--ink3);}} .cb-dday.today{{background:var(--accent);}} .cb-dday.soon{{background:var(--accent2);}} .cb-dday.future{{background:var(--ink2);}}
.cb-info{{flex:1;min-width:0;}}
.cb-artist{{font-size:14px;font-weight:700;margin-bottom:1px;}}
.cb-album{{font-size:12px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.cb-meta{{text-align:right;flex-shrink:0;}}
.cb-label{{font-size:10px;color:var(--ink3);letter-spacing:0.05em;margin-bottom:3px;}}
.cb-type{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:2px;letter-spacing:0.04em;display:inline-block;}}
.type-album{{background:#EDE7F6;color:#4527A0;}} .type-mini{{background:#E3F2FD;color:#1565C0;}} .type-single{{background:#E8F5E9;color:#2E7D32;}} .type-ep{{background:#FFF8E1;color:#F57F17;}}
.mv-wrap{{background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:1.1rem 1.25rem;}}
.mv-row{{display:flex;align-items:center;gap:12px;margin-bottom:11px;}}
.mv-row:last-of-type{{margin-bottom:0;}}
.mv-rank{{font-family:'Playfair Display',serif;font-size:13px;color:var(--ink3);min-width:18px;text-align:right;flex-shrink:0;}}
.mv-info{{flex:1;min-width:0;}}
.mv-title{{font-size:13px;font-weight:500;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-decoration:none;display:block;}}
.mv-title:hover{{color:var(--accent);}}
.mv-ch{{font-size:10px;color:var(--ink3);margin-top:1px;}}
.mv-bar-wrap{{width:120px;flex-shrink:0;}}
.mv-bar-track{{height:4px;background:#EBEBEB;border-radius:99px;overflow:hidden;margin-bottom:3px;}}
.mv-bar-fill{{height:100%;border-radius:99px;}}
.mv-views{{font-size:11px;font-weight:700;color:var(--ink2);text-align:right;}}
.mv-new{{font-size:9px;font-weight:700;padding:1px 5px;background:var(--accent);color:#fff;border-radius:2px;margin-left:5px;vertical-align:middle;letter-spacing:0.04em;}}
.mv-foot{{font-size:10px;color:var(--ink3);margin-top:10px;padding-top:10px;border-top:1px solid var(--rule2);}}
.news-grid{{display:flex;flex-direction:column;gap:6px;}}
.news-card{{display:flex;gap:12px;background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:0.85rem 1.1rem;text-decoration:none;transition:border-color 0.12s,background 0.12s;align-items:flex-start;}}
.news-card:hover{{border-color:var(--ink2);background:#F5F3F0;}}
.news-num{{font-family:'Playfair Display',serif;font-size:16px;color:#DCDCDC;font-weight:700;min-width:24px;flex-shrink:0;line-height:1.4;}}
.news-body{{flex:1;min-width:0;}}
.news-tags{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:5px;}}
.tag{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;letter-spacing:0.06em;text-transform:uppercase;}}
.tag-comeback{{background:#FBE9E7;color:#BF360C;}} .tag-chart{{background:#E3F2FD;color:#1565C0;}} .tag-global{{background:#E8F5E9;color:#1B5E20;}} .tag-brand{{background:#F3E5F5;color:#6A1B9A;}} .tag-concert{{background:#FFF3E0;color:#E65100;}} .tag-biz{{background:#ECEFF1;color:#263238;}} .tag-tech{{background:#E0F7FA;color:#006064;}}
.news-headline{{font-size:13px;font-weight:500;color:var(--ink);line-height:1.5;margin-bottom:3px;}}
.news-meta-row{{display:flex;align-items:center;gap:8px;margin-top:4px;}}
.news-source{{font-size:10px;color:var(--ink3);font-weight:500;}}
.news-arrow{{font-size:10px;color:var(--ink3);margin-left:auto;flex-shrink:0;}}
.footer{{border-top:1px solid var(--rule);padding-top:1.25rem;display:flex;align-items:center;justify-content:space-between;font-size:10px;color:var(--ink3);letter-spacing:0.06em;}}
.footer a{{color:var(--ink3);text-decoration:none;}}
.footer a:hover{{color:var(--ink);}}
@media(max-width:560px){{
  .masthead{{flex-direction:column;align-items:flex-start;}}
  .masthead-right{{text-align:left;}}
  .mv-bar-wrap{{width:80px;}}
  .cb-meta{{display:none;}}
}}
</style>
</head>
<body>
<div class="page">

  <div class="masthead">
    <div class="masthead-left">
      <div class="brand">K-pop Intelligence</div>
      <h1>케이팝 데일리<br><em>브리핑</em></h1>
    </div>
    <div class="masthead-right">
      <div class="date-block">
        <strong>{DAY_EN}</strong>
        {YEAR_EN} · {DAY_KO}요일<br>
        엔터산업 담당자용
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-head">
      <span class="section-num">01</span>
      <span class="section-title">컴백 &amp; 신보 일정</span>
    </div>
    <div class="comeback-list">{cb_rows}</div>
  </div>

  <div class="section">
    <div class="section-head">
      <span class="section-num">02</span>
      <span class="section-title">MV 조회수 — 발매 1주 이내 신규 우선</span>
    </div>
    <div class="mv-wrap">
      {mv_rows}
      <div class="mv-foot">* 기획사 공식 채널 기준 · MV / M/V 영상 한정 · 매일 오전 8시 자동 업데이트</div>
    </div>
  </div>

  <div class="section">
    <div class="section-head">
      <span class="section-num">03</span>
      <span class="section-title">오늘의 K-pop 뉴스 클리핑 (최대 10건)</span>
    </div>
    <div class="news-grid">{news_rows}</div>
  </div>

  <div class="footer">
    <span>K-pop Intelligence · 매일 자동 업데이트</span>
    <span>
      <a href="../index.html">← 최신호</a>
      &nbsp;·&nbsp;
      <a href="../archive.html">아카이브</a>
    </span>
  </div>

</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# 5. 메인 실행
# ─────────────────────────────────────────────

def main():
    print(f"[{TODAY}] K-pop 데일리 브리핑 생성 시작...")
    api_key = os.environ["YOUTUBE_API_KEY"]

    print("  → 기획사 채널 ID 확인...")
    ch_map = resolve_channels(api_key)

    print("  → Spotify 컴백 일정 조회...")
    token     = get_spotify_token()
    comebacks = fetch_comebacks(token)
    print(f"     {len(comebacks)}건")

    print("  → YouTube MV 조회수 수집...")
    mvs = get_mv_list(comebacks, ch_map, api_key)
    print(f"     {len(mvs)}건 (신규 {sum(1 for m in mvs if m.get('is_new'))}건 포함)")

    print("  → 뉴스 클리핑...")
    news = fetch_news(max_n=10)
    print(f"     {len(news)}건")

    print("  → HTML 렌더링...")
    html = render(comebacks, mvs, news)
    out  = OUT_DIR / f"{TODAY}.html"
    out.write_text(html, encoding="utf-8")
    print(f"  → 완료: {out}")

if __name__ == "__main__":
    main()
