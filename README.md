# ⚡ MCP Hub

> AI 확장 서버(MCP) 디렉토리 — 매일 오전 9시 자동 업데이트

**수집 소스:** awesome-mcp-servers · mcp.so · mcpservers.org

---

## 📁 파일 구조

```
mcp-hub/
├── index.html                    ← 프론트엔드 (검색/필터 UI)
├── scraper.py                    ← 데이터 수집 스크립트
├── data/
│   └── mcp_list.json             ← 수집된 MCP 데이터 (자동 갱신)
└── .github/
    └── workflows/
        └── update.yml            ← 매일 09:00 KST 자동 실행
```

---

## 🚀 배포 방법 (GitHub Pages)

### 1단계 — 저장소 생성

```bash
git init
git add .
git commit -m "init: MCP Hub"
git remote add origin https://github.com/YOUR_NAME/mcp-hub.git
git push -u origin main
```

### 2단계 — GitHub Pages 활성화

1. 저장소 → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `/ (root)`
4. **Save** 클릭

→ `https://YOUR_NAME.github.io/mcp-hub` 로 접속 가능

### 3단계 — 자동 업데이트 확인

- `.github/workflows/update.yml` 이 **매일 09:00 KST**에 자동 실행
- `scraper.py` 가 3개 소스 크롤링 후 `data/mcp_list.json` 업데이트
- 변경사항 있으면 자동 commit & push → Pages 자동 재배포

---

## 🔧 수동 실행

```bash
pip install requests beautifulsoup4
python scraper.py
```

GitHub Actions 탭에서 **workflow_dispatch** 로 수동 실행도 가능

---

## 📊 기능

| 기능 | 설명 |
|---|---|
| 검색 | 이름, 설명, 카테고리 실시간 검색 |
| 카테고리 필터 | 개발/DevOps, DB, 커뮤니케이션 등 12개 |
| 소스 필터 | awesome-mcp-servers / mcp.so / mcpservers.org |
| 정렬 | 스타 수 / 이름 / 소스 |
| 변경 감지 | 신규 추가/제거된 서버 배너로 표시 |
| 자동 업데이트 | GitHub Actions cron (매일 09:00 KST) |

---

## ⚙️ 커스터마이징

### 업데이트 시간 변경 (`update.yml`)
```yaml
# 매일 오전 6시 KST = UTC 21:00 전날
- cron: "0 21 * * *"
```

### 새 소스 추가 (`scraper.py`)
`scrape_*` 함수를 추가하고 `main()` 의 `raw` 리스트에 포함

### 카테고리 추가 (`scraper.py`)
`CATEGORY_KW` 딕셔너리에 키워드 추가
