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
BESTBLOGS_API_KEY = os.environ.get("BESTBLOGS_API_KEY", "")

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

def fetch_bestblogs():
    """通过 BestBlogs 官方 API 获取内容（免费版：公共早报 + 精选列表）"""
    items = []
    if not BESTBLOGS_API_KEY:
        print("[bestblogs] 未配置 API Key，跳过")
        return items

    api_headers = {
        "Authorization": f"Bearer {BESTBLOGS_API_KEY}",
        "Content-Type": "application/json"
    }

    def extract_items(data, source_name):
        """从 API 响应中提取文章列表，兼容多种返回结构"""
        result = []
        # 尝试各种可能的字段名
        for key in ["resources", "items", "data", "articles", "list"]:
            resources = data.get(key, [])
            if resources and isinstance(resources, list):
                for r in resources:
                    if not isinstance(r, dict):
                        continue
                    title = (r.get("title") or r.get("name") or r.get("headline") or "").strip()
                    url = (r.get("url") or r.get("link") or r.get("sourceUrl") or "").strip()
                    if title and url and url.startswith("http") and not is_paywalled(url):
                        result.append({"title": title, "url": url, "source": source_name})
                break
        return result

    # 1. 公共早报（今天）
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        res = requests.get(
            f"https://bestblogs.dev/api/v2/brief?date={today_str}&flavor=public",
            headers=api_headers, timeout=15
        )
        print(f"[bestblogs早报] 状态码: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            brief_items = extract_items(data, "BestBlogs早报")
            # 早报可能直接是文章对象列表
            if not brief_items and isinstance(data, list):
                for r in data:
                    if isinstance(r, dict):
                        title = (r.get("title") or r.get("name") or "").strip()
                        url = (r.get("url") or r.get("link") or "").strip()
                        if title and url and not is_paywalled(url):
                            brief_items.append({"title": title, "url": url, "source": "BestBlogs早报"})
            items += brief_items[:15]
            print(f"[bestblogs早报] 获取到 {len(brief_items[:15])} 条")
        else:
            print(f"[bestblogs早报] 响应: {res.text[:200]}")
    except Exception as e:
        print(f"[bestblogs早报] 失败: {e}")

    # 2. 精选内容列表（最近24小时，AI相关）
    try:
        res = requests.get(
            "https://bestblogs.dev/api/v2/resources?type=article&time=24h&language=all&qualified=true&limit=20",
            headers=api_headers, timeout=15
        )
        print(f"[bestblogs精选] 状态码: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            resource_items = extract_items(data, "BestBlogs精选")
            items += resource_items[:15]
            print(f"[bestblogs精选] 获取到 {len(resource_items[:15])} 条")
        else:
            print(f"[bestblogs精选] 响应: {res.text[:200]}")
    except Exception as e:
        print(f"[bestblogs精选] 失败: {e}")

    print(f"[bestblogs] 共获取 {len(items)} 条")
    return items


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


# AI 相关关键词，用于第一层预过滤
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "claude", "gemini", "openai", "anthropic", "deepseek",
    "chatgpt", "copilot", "agent", "model", "neural", "transformer",
    "robot", "automation", "ml ", "nlp", "diffusion", "midjourney",
    "stable diffusion", "hugging face", "nvidia", "gpu", "inference",
    "人工智能", "大模型", "机器学习", "深度学习", "语言模型", "智能体",
    "算法", "训练", "推理", "生成式", "多模态", "向量", "embedding",
]

def is_ai_related(title):
    """预判断标题是否与AI相关"""
    title_lower = title.lower()
    return any(kw in title_lower for kw in AI_KEYWORDS)


def collect_all_content():
    print("开始抓取内容源...")
    all_items = []

    # 高价值来源：全量抓取不限制
    all_items += fetch_bestblogs()
    all_items += fetch_rss("https://www.anthropic.com/news.rss", "Anthropic", limit=20)
    all_items += fetch_rss("https://openai.com/blog/rss.xml", "OpenAI", limit=20)
    all_items += fetch_rss("https://blog.google/technology/ai/rss/", "Google AI", limit=20)

    # 中文AI专媒：全量抓取（本身已是AI内容）
    all_items += fetch_rss("https://www.jiqizhixin.com/rss", "机器之心", limit=20)
    all_items += fetch_rss("https://www.qbitai.com/feed", "量子位", limit=20)
    all_items += fetch_rss("https://36kr.com/feed", "36氪", limit=20)

    # 综合科技媒体：先抓多条再预过滤AI相关
    techcrunch_raw = fetch_rss("https://techcrunch.com/feed/", "TechCrunch", limit=30)
    all_items += [i for i in techcrunch_raw if is_ai_related(i["title"])]

    verge_raw = fetch_rss("https://www.theverge.com/rss/index.xml", "The Verge", limit=30)
    all_items += [i for i in verge_raw if is_ai_related(i["title"])]

    hn_raw = fetch_hackernews()
    all_items += [i for i in hn_raw if is_ai_related(i["title"])]

    # AI变现/产品：预过滤
    ph_raw = fetch_rss("https://www.producthunt.com/feed", "ProductHunt", limit=30)
    all_items += [i for i in ph_raw if is_ai_related(i["title"])]

    ih_raw = fetch_rss("https://www.indiehackers.com/feed.rss", "IndieHackers", limit=20)
    all_items += [i for i in ih_raw if is_ai_related(i["title"])]

    # 去重（按标题前20字）
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"共抓取 {len(unique)} 条AI相关内容（已预过滤+去重）")
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

以下内容已经过AI关键词预过滤，请进一步处理并以JSON格式输出日报。

处理规则：
1. 【翻译】所有英文标题必须翻译成准确流畅的中文
2. 【优先级】优先展示以下来源的内容（排在前面）：
   Anthropic > OpenAI > Google AI > 机器之心 > 量子位 > 36氪 > TechCrunch > The Verge > BestBlogs早报 > BestBlogs精选 > 其他
3. 【分类】按主题分类，每个分类不限条数，有多少放多少
4. 【去重】相同事件不同来源只保留优先级最高的那条
5. 没有相关内容的分类返回空数组
6. 只输出JSON，不要任何其他文字

输出格式：
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

def build_text_report(data):
    """把结构化数据转成纯文本日报"""
    today = data.get("date", "")
    lines = [f"📬 AI日报 · {today}", ""]
    for section in data.get("sections", []):
        if not section.get("items"):
            continue
        lines.append(section["title"])
        for item in section["items"]:
            lines.append(f"• {item['title']}")
            lines.append(f"  {item['url']}")
        lines.append("")
    lines.append("— 由AI日报机器人自动生成")
    return "\n".join(lines)


def push_notification(data):
    today = data.get("date", datetime.now().strftime("%Y年%m月%d日"))
    text_report = build_text_report(data)

    # 飞书推送（富文本卡片，完整日报内容）
    if FEISHU_WEBHOOK:
        try:
            # 构建飞书卡片消息
            elements = []
            for section in data.get("sections", []):
                if not section.get("items"):
                    continue
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**{section['title']}**"}
                })
                for item in section["items"]:
                    elements.append({
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"[{item['title']}]({item['url']})  `{item['source']}`"
                        }
                    })
                elements.append({"tag": "hr"})

            card_payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"📬 AI日报 · {today}"},
                        "template": "purple"
                    },
                    "elements": elements + [{
                        "tag": "note",
                        "elements": [{"tag": "plain_text", "content": "由AI日报机器人自动生成"}]
                    }]
                }
            }
            res = requests.post(FEISHU_WEBHOOK, json=card_payload, timeout=15).json()
            if res.get("code") == 0:
                print("飞书推送成功！")
            else:
                # 降级为纯文本
                res2 = requests.post(FEISHU_WEBHOOK, json={
                    "msg_type": "text",
                    "content": {"text": text_report}
                }, timeout=15).json()
                print(f"飞书卡片失败，纯文本推送: {res2.get('code')}")
        except Exception as e:
            print(f"飞书推送异常: {e}")

    # 微信推送（只发一条短消息+链接，避免乱码和超长）
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
            pages_url = "https://ivy0070923.github.io/ai-daily-report/"

            # 只发一条纯文字通知+链接（无emoji，避免乱码）
            msg = f"AI日报 {today} 已更新\n点击查看完整内容：\n{pages_url}"

            success = 0
            for openid in openids:
                try:
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
                except Exception as e:
                    print(f"  微信发送给 {openid[:8]}... 异常: {e}")

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
    push_notification(data)

    print("全部完成！")


if __name__ == "__main__":
    main()
