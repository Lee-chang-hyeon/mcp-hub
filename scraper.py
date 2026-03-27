"""
MCP Hub 스크래퍼 v3 - 안정화 버전
수집 소스:
  1. GitHub awesome-mcp-servers (wong2 only)  ~500개
  2. GitHub API 검색 (topic:mcp-server)       ~300개
  3. Smithery API (retry + backoff)           ~500개
  4. mcp.so (수정된 파싱)                     ~200개
"""

import requests, json, re, time, os
from datetime import datetime, timezone
from bs4 import BeautifulSoup

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GH_HEADERS   = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {"Accept": "application/vnd.github.v3+json"}
WEB_HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; MCPHub/3.0)"}
DATA_PATH    = "data/mcp_list.json"

CATEGORY_KW = {
    "개발/DevOps":        ["github","gitlab","git","docker","ci","kubernetes","devops","terraform","jenkins","vercel","netlify","aws","gcp","azure","heroku","cloudflare"],
    "데이터베이스":        ["postgres","mysql","sqlite","mongodb","redis","supabase","database","db","sql","nosql","airtable","neon"],
    "브라우저 자동화":     ["playwright","puppeteer","browser","selenium","scraping","crawl","headless","automation"],
    "파일/시스템":         ["filesystem","file","storage","s3","drive","dropbox","onedrive","gdrive"],
    "커뮤니케이션":        ["slack","discord","telegram","whatsapp","gmail","email","chat","message","teams"],
    "검색/웹":             ["search","fetch","web","scrape","brave","firecrawl","perplexity","tavily"],
    "AI/데이터":           ["ai","llm","openai","anthropic","embedding","vector","memory","knowledge","huggingface","pinecone"],
    "생산성":              ["notion","calendar","todo","task","jira","asana","trello","linear","obsidian","todoist"],
    "디자인/크리에이티브": ["figma","canva","image","design","svg","stable diffusion","midjourney","dalle"],
    "비즈니스":            ["stripe","salesforce","crm","payment","shopify","analytics","finance","hubspot"],
    "모니터링/보안":       ["monitoring","logging","security","sentry","datadog","alert","metric","prometheus"],
}

def guess_category(name, desc):
    text = (name + " " + desc).lower()
    for cat, kws in CATEGORY_KW.items():
        if any(k in text for k in kws):
            return cat
    return "기타"

def parse_repo(url):
    if not url: return None
    m = re.search(r"github\.com/([^/]+/[^/\s#?]+)", url or "")
    return m.group(1).rstrip(".git") if m else None

def req(url, params=None, retries=3, delay=2):
    for i in range(retries):
        try:
            r = requests.get(url, headers=GH_HEADERS if "api.github.com" in url else WEB_HEADERS,
                           params=params, timeout=15)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", delay * (i+1) * 2))
                print(f"   rate limit → {wait}s 대기...")
                time.sleep(wait)
                continue
            return r
        except Exception as e:
            if i < retries-1: time.sleep(delay)
    return None

# ① awesome-mcp-servers (wong2만)
def scrape_awesome():
    print("📡 [1/4] awesome-mcp-servers...")
    results, seen = [], set()
    try:
        r = req("https://raw.githubusercontent.com/wong2/awesome-mcp-servers/main/README.md")
        if not r or r.status_code != 200:
            print(f"   ⚠ HTTP {r.status_code if r else 'no response'}")
            return results
        for m in re.finditer(r"-\s+\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–]?\s*(.+?)(?=\n|$)", r.text, re.M):
            name = m.group(1).strip()
            link = m.group(2).strip()
            desc = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", m.group(3).strip())[:200]
            key  = name.lower()
            if key in seen or len(name) < 2: continue
            seen.add(key)
            results.append({"name":name,"desc":desc,"url":link,"repo":parse_repo(link),
                           "source":"awesome-mcp-servers","cat":guess_category(name,desc),"stars":0})
    except Exception as e:
        print(f"   ⚠ {e}")
    print(f"   → {len(results)}개")
    return results

# ② GitHub API - topic 검색
def scrape_github_topics():
    print("📡 [2/4] GitHub topic:mcp-server 검색...")
    results, seen = [], set()
    topics = ["mcp-server","model-context-protocol","mcp-servers","claude-mcp"]
    for topic in topics:
        page = 1
        while page <= 5:
            r = req("https://api.github.com/search/repositories",
                   params={"q":f"topic:{topic}","sort":"stars","per_page":100,"page":page})
            if not r or r.status_code != 200: break
            data = r.json()
            items = data.get("items", [])
            if not items: break
            for item in items:
                name = item.get("name","").replace("-mcp","").replace("mcp-","").replace("_"," ").title()
                desc = (item.get("description") or "")[:200]
                url  = item.get("html_url","")
                repo = item.get("full_name")
                key  = repo or name.lower()
                if key in seen or len(name) < 2: continue
                seen.add(key)
                results.append({"name":name,"desc":desc,"url":url,"repo":repo,
                               "source":"github-topics","cat":guess_category(name,desc),
                               "stars":item.get("stargazers_count",0)})
            if len(items) < 100: break
            page += 1
            time.sleep(0.5)
    print(f"   → {len(results)}개")
    return results

# ③ Smithery (retry 강화)
def scrape_smithery():
    print("📡 [3/4] Smithery...")
    results, seen = [], set()
    # 공개 검색 엔드포인트 여러 개 시도
    endpoints = [
        "https://smithery.ai/api/v1/servers",
        "https://smithery.ai/api/servers",
        "https://registry.smithery.ai/servers",
    ]
    for endpoint in endpoints:
        page = 1
        while page <= 20:
            r = req(endpoint, params={"page":page,"pageSize":100,"limit":100})
            if not r or r.status_code not in (200,):
                break
            try: data = r.json()
            except: break
            items = data.get("servers") or data.get("items") or data.get("data") or (data if isinstance(data,list) else [])
            if not items: break
            new = 0
            for item in items:
                name = (item.get("name") or item.get("displayName") or item.get("qualifiedName") or "").strip()
                desc = (item.get("description") or "")[:200]
                url  = item.get("homepage") or item.get("url") or f"https://smithery.ai/server/{item.get('qualifiedName','')}"
                repo = parse_repo(item.get("repository") or url)
                key  = name.lower()
                if key in seen or len(name) < 2: continue
                seen.add(key)
                results.append({"name":name,"desc":desc,"url":url,"repo":repo,
                               "source":"smithery","cat":guess_category(name,desc),
                               "stars":item.get("stars",0)})
                new += 1
            total = data.get("total") or data.get("totalCount")
            if new == 0 or (total and len(results) >= int(total)): break
            page += 1
            time.sleep(1)
        if results: break
    print(f"   → {len(results)}개")
    return results

# ④ mcp.so (수정된 파싱)
def scrape_mcpso():
    print("📡 [4/4] mcp.so...")
    results, seen = [], set()
    for page in range(1, 15):
        url = f"https://mcp.so{'/?page='+str(page) if page>1 else '/'}"
        r   = req(url)
        if not r or r.status_code != 200: break
        soup = BeautifulSoup(r.text, "html.parser")
        # 다양한 셀렉터 시도
        cards = (soup.select("a[href*='/server']") or
                 soup.select("[class*='card']") or
                 soup.select("article"))
        if not cards: break
        new = 0
        for card in cards:
            name_el = card.find(["h2","h3","h4","strong"]) or card.find(class_=re.compile(r"title|name",re.I))
            if not name_el: continue
            name = name_el.get_text(strip=True)
            desc = (card.find("p") or card.find(class_=re.compile(r"desc",re.I)))
            desc = desc.get_text(strip=True)[:200] if desc else ""
            href = card.get("href","")
            link = ("https://mcp.so" + href) if href.startswith("/") else href
            key  = name.lower()
            if key in seen or len(name) < 2: continue
            seen.add(key)
            results.append({"name":name,"desc":desc,"url":link,"repo":parse_repo(link),
                           "source":"mcp.so","cat":guess_category(name,desc),"stars":0})
            new += 1
        print(f"   page {page}: {new}개", end="\r")
        if new == 0: break
        time.sleep(0.5)
    print(f"\n   → {len(results)}개")
    return results

def merge(lists):
    merged = {}
    pri = {"github-topics":0,"awesome-mcp-servers":1,"smithery":2,"mcp.so":3}
    for items in lists:
        for item in items:
            key = re.sub(r"[\s\-_.]","", item["name"].lower())
            if key not in merged:
                merged[key] = item
            else:
                ex = merged[key]
                if pri.get(item["source"],9) < pri.get(ex["source"],9):
                    item["stars"] = max(item["stars"], ex["stars"])
                    merged[key] = item
                else:
                    ex["stars"] = max(ex["stars"], item["stars"])
                    if len(item["desc"]) > len(ex["desc"]): ex["desc"] = item["desc"]
                    if item.get("repo") and not ex.get("repo"): ex["repo"] = item["repo"]
    result = list(merged.values())
    result.sort(key=lambda x: x["stars"], reverse=True)
    return result

def main():
    print("="*50)
    print("  🚀 MCP Hub 스크래퍼 v3")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*50+"\n")

    existing = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    old = existing.get("items", [])

    raw = [scrape_awesome(), scrape_github_topics(), scrape_smithery(), scrape_mcpso()]

    print("\n🔀 병합 중...")
    merged = merge(raw)

    from collections import Counter
    src_cnt = Counter(i["source"] for i in merged)
    print(f"\n📊 소스별: {dict(src_cnt)}")
    print(f"   기존 {len(old)}개 → 신규 {len(merged)}개 (+{len(merged)-len(old)})")

    os.makedirs("data", exist_ok=True)
    out = {"updated_at": datetime.now(timezone.utc).isoformat(),
           "total": len(merged),
           "sources": ["awesome-mcp-servers","github-topics","smithery","mcp.so"],
           "items": merged}
    with open(DATA_PATH,"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료 → {DATA_PATH} ({len(merged)}개)")

if __name__ == "__main__":
    main()