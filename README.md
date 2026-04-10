# K-pop Intelligence Newsletter

엔터산업 담당자를 위한 K-pop 자동 일간 브리핑.
Spotify / YouTube / 외신 RSS를 매일 수집하고 Claude AI로 요약해 GitHub Pages에 배포합니다.

---

## 구조

```
kpop-newsletter/
├── newsletters/          ← 생성된 HTML (날짜별)
│   └── 2026-04-10.html
├── scripts/
│   └── generate.py       ← 핵심 자동화 스크립트
└── .github/
    └── workflows/
        └── daily.yml     ← GitHub Actions (매일 오전 8시 KST)
```

---

## 1단계 — API 키 발급

| API | 발급 경로 | 비용 |
|-----|-----------|------|
| Spotify | https://developer.spotify.com → 앱 생성 → Client ID / Secret | 무료 |
| YouTube Data v3 | https://console.cloud.google.com → API 활성화 → 키 발급 | 무료 (할당량 내) |
| Anthropic | https://console.anthropic.com | 소량 유료 (월 몇 천원) |

---

## 2단계 — GitHub 저장소 설정

1. GitHub에 새 저장소 생성 (예: `kpop-newsletter`)
2. 이 폴더 내용을 전부 업로드
3. **Settings → Secrets and variables → Actions**에서 아래 4개 Secret 추가:

```
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
YOUTUBE_API_KEY
ANTHROPIC_API_KEY
```

---

## 3단계 — GitHub Pages 활성화

**Settings → Pages → Source: Deploy from a branch → main / (root)**

활성화 후 주소: `https://[내 GitHub 아이디].github.io/kpop-newsletter/`

---

## 4단계 — 첫 실행 테스트

GitHub Actions 탭 → `K-pop Intelligence Daily` → **Run workflow** 클릭

정상 실행되면 `newsletters/오늘날짜.html`이 자동 생성됩니다.

---

## 아티스트 추가하기

`scripts/generate.py` 상단의 `ARTISTS` 딕셔너리에 추가:

```python
ARTISTS = {
    "BINI":  "6MdRFpKXAMbBr88b1T3UM7",   # Spotify Artist ID
    "No Na": "여기에_Artist_ID_입력",
    ...
}
```

Spotify Artist ID 찾는 법: Spotify 앱에서 아티스트 페이지 → 공유 → 링크 복사
→ `https://open.spotify.com/artist/[이게 Artist ID]`

---

## 비용 예상

| 항목 | 월 예상 비용 |
|------|-------------|
| GitHub Actions | 무료 (월 2,000분 무료) |
| GitHub Pages | 무료 |
| Spotify API | 무료 |
| YouTube API | 무료 (하루 10,000 유닛, 충분) |
| Anthropic API | 약 ₩2,000–5,000/월 (기사 30개 × 30일 기준) |
