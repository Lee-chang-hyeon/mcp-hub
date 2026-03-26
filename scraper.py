"""
MCP Hub 자동 수집 스크래퍼 v2
소스:
  1. GitHub awesome-mcp-servers (README 파싱)   ~500개
  2. Smithery API (공식 페이지네이션 API)        ~1,500개
  3. mcp.so (HTML 파싱 + 페이지네이션)           ~300개
  4. mcpservers.org (HTML 파싱)                  ~200개
총합계 중복제거 후 약 2,000~2,500개 예상

실행: python scraper.py
      → data/mcp_list.json 자동 생성/업데이트
"""

import requests
import json
import re
import time
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS_GH   = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
} if GITHUB_TOKEN else {}
HEADERS_WEB  = {"User-Agent": "Mozilla/5.0 (compatible; MCPHub-Bot/2.0; +https://github.com)"}
DATA_PATH    = "data/mcp_list.json"
REQUEST_TIMEOUT = 15

CATEGORY_KW = {
    "개발/DevOps":        ["github","gitlab","git","docker","ci/cd","kubernetes","deployment","devops","terraform","jenkins","vercel","netlify","aws","gcp","azure","heroku","cloudflare"],
    "데이터베이스":        ["postgres","mysql","sqlite","mongodb","redis","supabase","database","db","sql","nosql","airtable","neon","planetscale","turso"],
    "브라우저 자동화":     ["playwright","puppeteer","browser","selenium","scraping","crawl","web automation","chromium","headless"],
    "파일/시스템":         ["filesystem","file","storage","s3","drive","dropbox","onedrive","directory","gdrive","box"],
    "커뮤니케이션":        ["slack","discord","telegram","whatsapp","gmail","email","chat","message","teams","twilio","line","kakao"],
    "검색/웹":             ["search","fetch","web","scrape","brave","bing","google search","firecrawl","crawl","perplexity","tavily"],
    "AI/데이터":           ["ai","llm","openai","anthropic","embedding","vector","memory","knowledge","ml","huggingface","replicate","cohere","pinecone"],
    "생산성":              ["notion","calendar","todo","task","jira","asana","trello","linear","project","obsidian","todoist","clickup"],
    "디자인/크리에이티브": ["figma","canva","image","design","svg","ui","graphic","stable diffusion","midjourney","dalle","runway"],
    "비즈니스":            ["stripe","salesforce","crm","payment","shopify","analytics","finance","accounting","hubspot","quickbooks","xero"],
    "모니터링/보안":       ["monitoring","logging","security","sentry","datadog","alert","metric","prometheus","grafana","pagerduty"],
}

def guess_category(name: str, desc: str) -> str:
    text = (name + " " + desc).lower()
    for cat, kws in CATEGORY_KW.items():
        if any(k in text for k in kws):
            return cat
    return "기타"

def get_github_stars(repo: str) -> int:
    if not GITHUB_TOKEN or not repo:
        return 0
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}",
            headers=HEADERS_GH,
            timeout=8
        )
        if r.status_code == 200:
            return r.json().get("stargazers_count", 0)
        elif r.status_code == 403:
            print("   ⚠ GitHub API rate limit 도달")
    except Exception:
        pass
    return 0

def parse_github_url(url: str):
    if not url:
        return None
    m = re.search(r"github\.com/([^/]+/[^/\s#?]+)", url)
    return m.group(1).rstrip(".git") if m else None

# ════════════════════════════════════════════════════════════
# ① awesome-mcp-servers (GitHub README)
# ════════════════════════════════════════════════════════════
def scrape_awesome_mcp_servers() -> list:
    print("📡 [1/4] awesome-mcp-servers 수집 중...")
    results = []
    urls = [
        "https://raw.githubusercontent.com/wong2/awesome-mcp-servers/main/README.md",
        "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md",
    ]
    seen = set()
    for url in urls:
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            content = r.text

            pattern = re.compile(
                r"-\s+\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–—]?\s*(.+?)(?=\n|$)",
                re.MULTILINE
            )
            for m in pattern.finditer(content):
                name = m.group(1).strip()
                link = m.group(2).strip()
                desc = m.group(3).strip()
                desc = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", desc)
                desc = re.sub(r"`([^`]+)`", r"\1", desc)
                desc = desc[:200]

                key = name.lower()
                if key in seen or len(name) < 2:
                    continue
                seen.add(key)

                repo = parse_github_url(link)
                results.append({
                    "name": name, "desc": desc, "url": link,
                    "repo": repo, "source": "awesome-mcp-servers",
                    "cat": guess_category(name, desc), "stars": 0,
                })
        except Exception as e:
            print(f"   ⚠ 오류 ({url}): {e}")

    print(f"   → {len(results)}개 수집")
    return results

# ════════════════════════════════════════════════════════════
# ② Smithery API (공식 페이지네이션)
# ════════════════════════════════════════════════════════════
def scrape_smithery() -> list:
    print("📡 [2/4] Smithery API 수집 중...")
    results = []
    seen    = set()
    page    = 1
    per_page = 100
    max_pages = 30   # 최대 3,000개 시도

    while page <= max_pages:
        try:
            # Smithery 공개 검색 API
            r = requests.get(
                "https://smithery.ai/api/v1/servers",
                params={"page": page, "pageSize": per_page},
                headers=HEADERS_WEB,
                timeout=REQUEST_TIMEOUT
            )
            if r.status_code == 404:
                # 엔드포인트 대안 시도
                r = requests.get(
                    f"https://smithery.ai/api/servers?page={page}&limit={per_page}",
                    headers=HEADERS_WEB,
                    timeout=REQUEST_TIMEOUT
                )

            if r.status_code != 200:
                print(f"   ⚠ Smithery HTTP {r.status_code} (page {page})")
                break

            data = r.json()

            # 응답 구조 유연하게 처리
            items = (
                data.get("servers") or
                data.get("items") or
                data.get("data") or
                (data if isinstance(data, list) else [])
            )
            if not items:
                break

            for item in items:
                name = (
                    item.get("name") or
                    item.get("displayName") or
                    item.get("title") or ""
                ).strip()
                desc = (
                    item.get("description") or
                    item.get("summary") or ""
                )[:200]
                url = (
                    item.get("url") or
                    item.get("homepage") or
                    item.get("repository") or
                    f"https://smithery.ai/server/{item.get('id','')}"
                )
                repo = parse_github_url(
                    item.get("repository") or
                    item.get("repo") or url
                )

                key = name.lower()
                if key in seen or len(name) < 2:
                    continue
                seen.add(key)

                results.append({
                    "name": name, "desc": desc, "url": url,
                    "repo": repo, "source": "smithery",
                    "cat": guess_category(name, desc),
                    "stars": item.get("stars") or item.get("stargazers_count") or 0,
                })

            print(f"   page {page}: {len(items)}개 → 누적 {len(results)}개", end="\r")

            # 마지막 페이지 확인
            total = data.get("total") or data.get("totalCount") or data.get("count")
            if total and len(results) >= int(total):
                break
            if len(items) < per_page:
                break

            page += 1
            time.sleep(0.3)

        except Exception as e:
            print(f"\n   ⚠ Smithery 오류 (page {page}): {e}")
            break

    print(f"\n   → {len(results)}개 수집")
    return results

# ════════════════════════════════════════════════════════════
# ③ mcp.so (HTML 파싱 + 페이지네이션)
# ════════════════════════════════════════════════════════════
def scrape_mcpso() -> list:
    print("📡 [3/4] mcp.so 수집 중...")
    results = []
    seen    = set()
    page    = 1

    while page <= 20:   # 최대 20페이지
        try:
            url = f"https://mcp.so/servers?page={page}" if page > 1 else "https://mcp.so/servers"
            r   = requests.get(url, headers=HEADERS_WEB, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("a", href=re.compile(r"^/server/|^/servers/"))

            if not cards:
                # 다른 셀렉터 시도
                cards = soup.find_all(["article", "div"], class_=re.compile(r"card|server|item", re.I))

            if not cards:
                break

            new_count = 0
            for card in cards:
                href     = card.get("href", "")
                name_el  = card.find(["h2","h3","h4","strong","span"], class_=re.compile(r"name|title", re.I)) or card.find(["h2","h3","h4","strong"])
                if not name_el:
                    continue
                name     = name_el.get_text(strip=True)
                desc_el  = card.find("p")
                desc     = desc_el.get_text(strip=True)[:200] if desc_el else ""
                link     = ("https://mcp.so" + href) if href.startswith("/") else href
                repo     = parse_github_url(link)

                key = name.lower()
                if key in seen or len(name) < 2:
                    continue
                seen.add(key)
                new_count += 1

                results.append({
                    "name": name, "desc": desc, "url": link,
                    "repo": repo, "source": "mcp.so",
                    "cat": guess_category(name, desc), "stars": 0,
                })

            print(f"   page {page}: {new_count}개 → 누적 {len(results)}개", end="\r")

            if new_count == 0:
                break
            page += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"\n   ⚠ mcp.so 오류 (page {page}): {e}")
            break

    print(f"\n   → {len(results)}개 수집")
    return results

# ════════════════════════════════════════════════════════════
# ④ mcpservers.org (HTML 파싱)
# ════════════════════════════════════════════════════════════
def scrape_mcpservers_org() -> list:
    print("📡 [4/4] mcpservers.org 수집 중...")
    results = []
    seen    = set()

    try:
        r    = requests.get("https://mcpservers.org", headers=HEADERS_WEB, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")

        for card in soup.find_all(["article","div"], class_=re.compile(r"card|server|item|plugin", re.I)):
            name_el = card.find(["h2","h3","h4","strong"])
            if not name_el:
                continue
            name    = name_el.get_text(strip=True)
            desc_el = card.find("p")
            desc    = desc_el.get_text(strip=True)[:200] if desc_el else ""
            link_el = card.find("a", href=re.compile(r"github\.com|https://"))
            url     = link_el["href"] if link_el else ""
            repo    = parse_github_url(url)

            key = name.lower()
            if key in seen or len(name) < 2:
                continue
            seen.add(key)

            results.append({
                "name": name, "desc": desc, "url": url,
                "repo": repo, "source": "mcpservers.org",
                "cat": guess_category(name, desc), "stars": 0,
            })

    except Exception as e:
        print(f"   ⚠ 오류: {e}")

    print(f"   → {len(results)}개 수집")
    return results

# ════════════════════════════════════════════════════════════
# 병합 / 중복 제거
# ════════════════════════════════════════════════════════════
def merge_and_deduplicate(lists: list) -> list:
    merged = {}
    # 소스 우선순위: smithery > awesome > mcp.so > mcpservers.org
    priority = {"smithery": 0, "awesome-mcp-servers": 1, "mcp.so": 2, "mcpservers.org": 3}

    for items in lists:
        for item in items:
            key = re.sub(r"[\s\-_]", "", item["name"].lower())
            if key not in merged:
                merged[key] = item
            else:
                existing = merged[key]
                # 더 높은 우선순위 소스로 덮어쓰기
                if priority.get(item["source"], 9) < priority.get(existing["source"], 9):
                    item["stars"] = max(item["stars"], existing["stars"])
                    merged[key] = item
                else:
                    if item["stars"] > existing["stars"]:
                        existing["stars"] = item["stars"]
                    if len(item["desc"]) > len(existing["desc"]):
                        existing["desc"] = item["desc"]
                    if item.get("repo") and not existing.get("repo"):
                        existing["repo"] = item["repo"]

    result = list(merged.values())
    result.sort(key=lambda x: x["stars"], reverse=True)
    return result

# ════════════════════════════════════════════════════════════
# GitHub 스타 수 조회
# ════════════════════════════════════════════════════════════
def enrich_stars(items: list) -> list:
    if not GITHUB_TOKEN:
        return items

    print("\n⭐ GitHub 스타 수 조회 중...")
    count = 0
    for item in items:
        if item.get("repo") and item["stars"] == 0:
            s = get_github_stars(item["repo"])
            if s > 0:
                item["stars"] = s
            count += 1
            if count % 20 == 0:
                print(f"   {count}개 처리 중...", end="\r")
            time.sleep(0.2)

    print(f"\n   → {count}개 스타 조회 완료")
    return items

# ════════════════════════════════════════════════════════════
# 변경 리포트
# ════════════════════════════════════════════════════════════
def diff_report(old_items: list, new_items: list):
    old_names = {i["name"].lower() for i in old_items}
    new_names = {i["name"].lower() for i in new_items}
    added     = new_names - old_names
    removed   = old_names - new_names

    print(f"\n{'─'*50}")
    print(f"  📊 변경 리포트")
    print(f"{'─'*50}")
    print(f"  기존    : {len(old_items):,}개")
    print(f"  신규 추가: +{len(added):,}개")
    print(f"  제거됨  : -{len(removed):,}개")
    print(f"  최종    : {len(new_items):,}개")

    if added:
        sample = list(added)[:5]
        print(f"  ✨ 새 서버: {', '.join(sample)}" + (f" 외 {len(added)-5}개" if len(added) > 5 else ""))
    if removed:
        sample = list(removed)[:5]
        print(f"  🗑  제거됨: {', '.join(sample)}" + (f" 외 {len(removed)-5}개" if len(removed) > 5 else ""))

# ════════════════════════════════════════════════════════════
# 소스별 통계
# ════════════════════════════════════════════════════════════
def source_stats(items: list):
    from collections import Counter
    src_count = Counter(i["source"] for i in items)
    cat_count = Counter(i["cat"] for i in items)

    print(f"\n  📦 소스별 수집 수")
    for src, cnt in src_count.most_common():
        print(f"     {src:<25} : {cnt:,}개")

    print(f"\n  🗂  카테고리별 수집 수")
    for cat, cnt in cat_count.most_common():
        print(f"     {cat:<20} : {cnt:,}개")

# ════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 50)
    print("  🚀 MCP Hub 데이터 수집 시작 v2")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if not GITHUB_TOKEN:
        print("  ⚠ GITHUB_TOKEN 없음 (스타 수 조회 생략)")
    print("=" * 50 + "\n")

    # 기존 데이터 로드
    existing = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    old_items = existing.get("items", [])

    # 4개 소스 수집
    raw = [
        scrape_awesome_mcp_servers(),
        scrape_smithery(),
        scrape_mcpso(),
        scrape_mcpservers_org(),
    ]

    # 병합/중복제거
    print("\n🔀 병합 및 중복 제거 중...")
    merged = merge_and_deduplicate(raw)

    # 스타 수 조회 (token 있을 때만)
    merged = enrich_stars(merged)

    # 변경 리포트 + 소스 통계
    diff_report(old_items, merged)
    source_stats(merged)

    # 저장
    os.makedirs("data", exist_ok=True)
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(merged),
        "sources": ["awesome-mcp-servers", "smithery", "mcp.so", "mcpservers.org"],
        "items": merged,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  ✅ 완료 → {DATA_PATH}")
    print(f"  총 {len(merged):,}개 저장")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()