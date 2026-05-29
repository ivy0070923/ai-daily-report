import os
import re
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
WX_TEST_APPID = os.environ.get("WX_TEST_APPID", "")
WX_TEST_SECRET = os.environ.get("WX_TEST_SECRET", "")
WX_TEST_OPENIDS = os.environ.get("WX_TEST_OPENIDS", "")
GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

PAYWALL_DOMAINS = [
    "ft.com", "wsj.com", "nytimes.com", "bloomberg.com",
    "economist.com", "thetimes.co.uk", "telegraph.co.uk",
    "hbr.org", "theatlantic.com", "wired.com", "businessinsider.com"
]

def is_paywalled(url):
    for domain in PAYWALL_DOMAINS:
        if domain in url:
            return True
    return False


# ============================================================
# 第一步：抓取各内容源
# ============================================================

def fetch_aihot_news():
    items = []
    try:
        res = requests.get("https://aihot.today/ai-news", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a[href]")[:30]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("http" in href or href.startswith("/")):
                url = href if href.startswith("http") else "https://aihot.today" + href
                if not is_paywalled(url):
                    items.append({"title": title, "url": url, "source": "aihot新闻"})
    except Exception as e:
        print(f"[aihot新闻] 抓取失败: {e}")
    return items[:15]


def fetch_aihot_events():
    items = []
    try:
        res = requests.get("https://aihot.today/ai-event", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a[href]")[:20]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("http" in href or href.startswith("/")):
                url = href if href.startswith("http") else "https://aihot.today" + href
                if not is_paywalled(url):
                    items.append({"title": title, "url": url, "source": "aihot活动"})
    except Exception as e:
        print(f"[aihot活动] 抓取失败: {e}")
    return items[:10]


def fetch_bestblogs():
    items = []
    urls = [
        ("https://www.bestblogs.dev/articles", "精选文章"),
        ("https://www.bestblogs.dev/videos", "精选视频"),
        ("https://www.bestblogs.dev/tweets", "精选推文"),
    ]
    for url, label in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select("a[href]")[:20]:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if len(title) > 10 and ("http" in href or href.startswith("/")):
                    full_url = href if href.startswith("http") else "https://www.bestblogs.dev" + href
                    if not is_paywalled(full_url):
                        items.append({"title": title, "url": full_url, "source": label})
        except Exception as e:
            print(f"[bestblogs {label}] 抓取失败: {e}")
    return items[:20]


def fetch_rss(url, source_name, limit=15):
    items = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "xml")
        entries = soup.select("item") or soup.select("entry")
        for entry in entries[:limit]:
            title = entry.find("title")
            link = entry.find("link")
            if title:
                t = title.get_text(strip=True)
                u = link.get_text(strip=True) if link and link.get_text(strip=True) else link.get("href", "") if link else ""
                if t and u and not is_paywalled(u):
                    items.append({"title": t, "url": u, "source": source_name})
    except Exception as e:
        print(f"[{source_name}] 抓取失败: {e}")
    return items


def fetch_hackernews():
    items = []
    try:
        res = requests.get("https://hacker-news.firebaseio.com/v0/newstories.json", timeout=10)
        story_ids = res.json()[:50]
        for sid in story_ids[:30]:
            story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
            if story and story.get("title"):
                url = story.get("url", f"https://news.ycombinator.com/item?id={sid}")
                if not is_paywalled(url):
                    items.append({"title": story["title"], "url": url, "source": "Hacker News"})
    except Exception as e:
        print(f"[Hacker News] 抓取失败: {e}")
    return items[:20]


def collect_all_content():
    print("开始抓取内容源...")
    all_items = []
    all_items += fetch_aihot_news()
    all_items += fetch_aihot_events()
    all_items += fetch_bestblogs()
    all_items += fetch_rss("https://techcrunch.com/feed/", "TechCrunch")
    all_items += fetch_rss("https://www.theverge.com/rss/index.xml", "The Verge")
    all_items += fetch_hackernews()
    all_items += fetch_rss("https://36kr.com/feed", "36氪")
    all_items += fetch_rss("https://www.jiqizhixin.com/rss", "机器之心")
    all_items += fetch_rss("https://www.qbitai.com/feed", "量子位")
    all_items += fetch_rss("https://www.anthropic.com/news.rss", "Anthropic")
    all_items += fetch_rss("https://openai.com/blog/rss.xml", "OpenAI")
    all_items += fetch_rss("https://blog.google/technology/ai/rss/", "Google AI")
    all_items += fetch_rss("https://www.producthunt.com/feed", "ProductHunt")
    all_items += fetch_rss("https://www.indiehackers.com/feed.rss", "IndieHackers")

    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"共抓取 {len(unique)} 条原始内容（已过滤付费墙）")
    return unique


# ============================================================
# 第二步：DeepSeek AI 过滤+翻译+总结（返回结构化数据）
# ============================================================

def ai_filter_and_summarize(items):
    today = datetime.now().strftime("%Y年%m月%d日")
    raw_text = ""
    for i, item in enumerate(items):
        raw_text += f"{i+1}. [{item['source']}] {item['title']}\n   链接：{item['url']}\n"

    prompt = f"""你是一个专业的AI行业日报编辑。今天是{today}。

请从以下原始内容中筛选AI相关内容，翻译成中文，并以JSON格式输出。

筛选主题：AI模型动态、AI应用产品、AI商业变现、AI企业动态、AI学习活动

输出格式（只输出JSON，不要任何其他文字）：
{{
  "date": "{today}",
  "sections": [
    {{
      "title": "🤖 模型与技术",
      "items": [
        {{"title": "文章标题中文", "url": "原文链接", "source": "来源"}}
      ]
    }},
    {{
      "title": "📱 应用与产品",
      "items": []
    }},
    {{
      "title": "💰 商业与变现",
      "items": []
    }},
    {{
      "title": "🏢 企业动态",
      "items": []
    }},
    {{
      "title": "🎓 学习与活动",
      "items": []
    }}
  ]
}}

每个分类最多5条，没有内容的分类返回空数组。

原始内容：
{raw_text}
"""

    try:
        res = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0.3
            },
            timeout=60
        )
        result = res.json()
        content = result["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        data = json.loads(content)
        print("AI总结完成")
        return data
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        return None


# ============================================================
# 第三步：生成精美 HTML 日报
# ============================================================

def generate_html(data):
    today = data.get("date", datetime.now().strftime("%Y年%m月%d日"))
    sections_html = ""

    for section in data.get("sections", []):
        if not section.get("items"):
            continue
        items_html = ""
        for item in section["items"]:
            items_html += f"""
            <div class="item">
                <a href="{item['url']}" target="_blank" class="item-title">{item['title']}</a>
                <span class="item-source">{item['source']}</span>
            </div>"""

        sections_html += f"""
        <div class="section">
            <h2 class="section-title">{section['title']}</h2>
            {items_html}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI日报 · {today}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
    background: #f0f2f5;
    color: #333;
    padding: 20px 16px;
  }}
  .container {{ max-width: 720px; margin: 0 auto; }}
  .header {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 28px 24px;
    margin-bottom: 20px;
    color: white;
  }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
  .header p {{ font-size: 13px; opacity: 0.85; }}
  .section {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }}
  .section-title {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f0f0f0;
    color: #1a1a2e;
  }}
  .item {{
    padding: 10px 0;
    border-bottom: 1px solid #f7f7f7;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
  }}
  .item:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .item-title {{
    font-size: 14px;
    color: #2d5be3;
    text-decoration: none;
    line-height: 1.5;
    flex: 1;
  }}
  .item-title:hover {{ text-decoration: underline; }}
  .item-source {{
    font-size: 11px;
    color: #999;
    white-space: nowrap;
    background: #f5f5f5;
    padding: 2px 8px;
    border-radius: 10px;
    margin-top: 2px;
  }}
  .footer {{
    text-align: center;
    font-size: 12px;
    color: #bbb;
    padding: 16px 0;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📬 AI日报</h1>
    <p>{today} · 自动抓取 · AI精选</p>
  </div>
  {sections_html}
  <div class="footer">由 AI日报机器人自动生成 · {today}</div>
</div>
</body>
</html>"""

    # 保存到 docs/index.html（GitHub Pages 默认读取 docs 目录）
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML日报生成完成：docs/index.html")
    return html


# ============================================================
# 第四步：推送通知（飞书 + 微信，只发链接）
# ============================================================

def push_notification(today):
    url = GITHUB_PAGES_URL or "https://ivy0070923.github.io/ai-daily-report/"
    msg = f"📬 AI日报 · {today}\n今日日报已生成，点击查看：\n{url}"

    # 飞书推送
    if FEISHU_WEBHOOK:
        try:
            res = requests.post(FEISHU_WEBHOOK, json={
                "msg_type": "text",
                "content": {"text": msg}
            }, timeout=15).json()
            if res.get("code") == 0:
                print("飞书推送成功！")
            else:
                print(f"飞书推送失败: {res}")
        except Exception as e:
            print(f"飞书推送异常: {e}")

    # 微信推送
    if WX_TEST_APPID and WX_TEST_SECRET and WX_TEST_OPENIDS:
        try:
            token_res = requests.get(
                f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WX_TEST_APPID}&secret={WX_TEST_SECRET}",
                timeout=10
            ).json()
            token = token_res.get("access_token")
            if not token:
                raise Exception(f"获取Token失败: {token_res}")

            openids = [o.strip() for o in WX_TEST_OPENIDS.split(",") if o.strip()]
            wx_url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
            success = 0
            for openid in openids:
                res = requests.post(wx_url, json={
                    "touser": openid,
                    "msgtype": "text",
                    "text": {"content": msg}
                }, timeout=15).json()
                if res.get("errcode") == 0:
                    success += 1
                    print(f"  微信发送给 {openid[:8]}... 成功")
                else:
                    print(f"  微信发送给 {openid[:8]}... 失败: {res}")
            print(f"微信推送完成：{success}/{len(openids)} 人成功")
        except Exception as e:
            print(f"微信推送异常: {e}")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 50)
    print(f"AI日报开始运行：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    items = collect_all_content()
    if not items:
        print("未抓取到任何内容，退出")
        return

    data = ai_filter_and_summarize(items)
    if not data:
        print("AI总结失败，退出")
        return

    generate_html(data)

    today = data.get("date", datetime.now().strftime("%Y年%m月%d日"))
    push_notification(today)

    print("全部完成！")


if __name__ == "__main__":
    main()
