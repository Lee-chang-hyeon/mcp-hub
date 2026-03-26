"""
MCP Hub 자동 수집 스크래퍼
소스: GitHub awesome-mcp-servers README + mcp.so + mcpservers.org
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
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
DATA_PATH = "data/mcp_list.json"

CATEGORY_KW = {
    "개발/DevOps":        ["github","gitlab","git","docker","ci/cd","kubernetes","deployment","devops","terraform","jenkins"],
    "데이터베이스":        ["postgres","mysql","sqlite","mongodb","redis","supabase","database","db","sql","nosql"],
    "브라우저 자동화":     ["playwright","puppeteer","browser","selenium","scraping","crawl","web automation"],
    "파일/시스템":         ["filesystem","file","storage","s3","drive","dropbox","onedrive","directory"],
    "커뮤니케이션":        ["slack","discord","telegram","whatsapp","gmail","email","chat","message","teams"],
    "검색/웹":             ["search","fetch","web","scrape","brave","bing","google search","firecrawl","crawl"],
    "AI/데이터":           ["ai","llm","openai","anthropic","embedding","vector","memory","knowledge","ml"],
    "생산성":              ["notion","calendar","todo","task","jira","asana","trello","linear","project","obsidian"],
    "디자인/크리에이티브": ["figma","canva","image","design","svg","ui","graphic","stable diffusion","midjourney"],
    "비즈니스":            ["stripe","salesforce","crm","payment","shopify","analytics","finance","accounting","hubspot"],
    "모니터링/보안":       ["monitoring","logging","security","sentry","datadog","alert","metric","prometheus"],
}

def guess_category(name: str, desc: str) -> str:
    text = (name + " " + desc).lower()
    for cat, kws in CATEGORY_KW.items():
        if any(k in text for k in kws):
            return cat
    return "기타"

def get_github_stars(repo: str) -> int:
    """GitHub repo 스타 수 조회"""
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get("stargazers_count", 0)
    except Exception:
        pass
    return 0

def parse_github_url(url: str):
    """URL에서 owner/repo 추출"""
    m = re.search(r"github\.com/([^/]+/[^/\s#?]+)", url)
    return m.group(1) if m else None

def scrape_awesome_mcp_servers() -> list:
    """GitHub wong2/awesome-mcp-servers README 파싱"""
    print("📡 awesome-mcp-servers 수집 중...")
    results = []
    try:
        url = "https://raw.githubusercontent.com/wong2/awesome-mcp-servers/main/README.md"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        content = r.text

        # 링크 패턴: - [이름](url) - 설명
        pattern = re.compile(
            r"-\s+\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–—]?\s*(.+?)(?=\n|$)",
            re.MULTILINE
        )
        seen = set()
        for m in pattern.finditer(content):
            name = m.group(1).strip()
            link = m.group(2).strip()
            desc = m.group(3).strip()

            # 마크다운 링크 제거
            desc = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", desc)
            desc = re.sub(r"`([^`]+)`", r"\1", desc)
            desc = desc[:200]

            key = name.lower()
            if key in seen or len(name) < 2:
                continue
            seen.add(key)

            repo = parse_github_url(link)
            results.append({
                "name": name,
                "desc": desc,
                "url": link,
                "repo": repo,
                "source": "awesome-mcp-servers",
                "cat": guess_category(name, desc),
                "stars": 0,
            })

        print(f"   → {len(results)}개 수집")
    except Exception as e:
        print(f"   ⚠ 오류: {e}")
    return results

def scrape_mcpso() -> list:
    """mcp.so 페이지 파싱"""
    print("📡 mcp.so 수집 중...")
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MCPHub-Bot/1.0)"}
        r = requests.get("https://mcp.so", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/servers/"):
                continue
            name_el = a.find(["h2", "h3", "strong", "span"])
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            desc_el = a.find("p")
            desc = desc_el.get_text(strip=True)[:200] if desc_el else ""
            link = "https://mcp.so" + href

            key = name.lower()
            if key in seen or len(name) < 2:
                continue
            seen.add(key)

            results.append({
                "name": name,
                "desc": desc,
                "url": link,
                "repo": None,
                "source": "mcp.so",
                "cat": guess_category(name, desc),
                "stars": 0,
            })

        print(f"   → {len(results)}개 수집")
    except Exception as e:
        print(f"   ⚠ 오류: {e}")
    return results

def scrape_mcpservers_org() -> list:
    """mcpservers.org 파싱"""
    print("📡 mcpservers.org 수집 중...")
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MCPHub-Bot/1.0)"}
        r = requests.get("https://mcpservers.org", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        seen = set()
        cards = soup.find_all(["article","div"], class_=re.compile(r"card|server|item", re.I))
        for card in cards:
            name_el = card.find(["h2","h3","h4","strong"])
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            desc_el = card.find("p")
            desc = desc_el.get_text(strip=True)[:200] if desc_el else ""
            link_el = card.find("a", href=re.compile(r"github\.com"))
            link = link_el["href"] if link_el else card.find("a", href=True)
            url = link["href"] if isinstance(link, dict) else (link or "")

            key = name.lower()
            if key in seen or len(name) < 2:
                continue
            seen.add(key)

            repo = parse_github_url(url) if url else None
            results.append({
                "name": name,
                "desc": desc,
                "url": url,
                "repo": repo,
                "source": "mcpservers.org",
                "cat": guess_category(name, desc),
                "stars": 0,
            })

        print(f"   → {len(results)}개 수집")
    except Exception as e:
        print(f"   ⚠ 오류: {e}")
    return results

def enrich_stars(items: list) -> list:
    """GitHub 스타 수 일괄 조회 (rate limit 고려)"""
    print("⭐ GitHub 스타 수 조회 중...")
    count = 0
    for item in items:
        repo = item.get("repo")
        if repo:
            item["stars"] = get_github_stars(repo)
            count += 1
            if count % 10 == 0:
                print(f"   {count}개 처리 중...", end="\r")
            time.sleep(0.3)   # rate limit 방지
    print(f"   → {count}개 스타 조회 완료")
    return items

def merge_and_deduplicate(lists: list) -> list:
    """소스별 데이터 병합 + 중복 제거"""
    merged = {}
    for items in lists:
        for item in items:
            key = item["name"].lower().strip()
            if key not in merged:
                merged[key] = item
            else:
                # 스타 수 큰 쪽 유지, 설명 더 긴 쪽 유지
                existing = merged[key]
                if item["stars"] > existing["stars"]:
                    existing["stars"] = item["stars"]
                if len(item["desc"]) > len(existing["desc"]):
                    existing["desc"] = item["desc"]
                if item.get("repo") and not existing.get("repo"):
                    existing["repo"] = item["repo"]
    result = list(merged.values())
    result.sort(key=lambda x: x["stars"], reverse=True)
    return result

def load_existing() -> dict:
    """기존 JSON 로드"""
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "updated_at": "", "total": 0}

def diff_report(old_items: list, new_items: list):
    """변경사항 리포트"""
    old_names = {i["name"].lower() for i in old_items}
    new_names = {i["name"].lower() for i in new_items}
    added   = new_names - old_names
    removed = old_names - new_names
    print(f"\n📊 변경 리포트")
    print(f"   신규 추가: {len(added)}개")
    print(f"   제거됨  : {len(removed)}개")
    print(f"   최종 총계: {len(new_items)}개")
    if added:
        print(f"   ✨ 새로 추가된 서버: {', '.join(list(added)[:10])}" + ("..." if len(added)>10 else ""))
    if removed:
        print(f"   🗑  제거된 서버: {', '.join(list(removed)[:10])}" + ("..." if len(removed)>10 else ""))

def main():
    print("=" * 55)
    print("  🚀 MCP Hub 데이터 수집 시작")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)

    existing = load_existing()
    old_items = existing.get("items", [])

    # 수집
    raw = [
        scrape_awesome_mcp_servers(),
        scrape_mcpso(),
        scrape_mcpservers_org(),
    ]

    # 병합/중복제거
    print("\n🔀 병합 및 중복 제거 중...")
    merged = merge_and_deduplicate(raw)

    # 스타 수 조회 (GitHub token 있을 때만 전체, 없으면 상위만)
    if GITHUB_TOKEN:
        merged = enrich_stars(merged)
    else:
        print("⚠ GITHUB_TOKEN 없음 → 스타 조회 생략 (Actions에서 자동 조회)")

    # 변경 리포트
    diff_report(old_items, merged)

    # 저장
    os.makedirs("data", exist_ok=True)
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(merged),
        "sources": ["awesome-mcp-servers", "mcp.so", "mcpservers.org"],
        "items": merged,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료 → {DATA_PATH} ({len(merged)}개 저장)")
    print("=" * 55)

if __name__ == "__main__":
    main()
