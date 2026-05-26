import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 付费墙域名黑名单，抓取后过滤掉
PAYWALL_DOMAINS = [
    "ft.com", "wsj.com", "nytimes.com", "bloomberg.com",
    "economist.com", "thetimes.co.uk", "telegraph.co.uk",
    "hbr.org", "theatlantic.com", "wired.com", "businessinsider.com"
]

def is_paywalled(url):
    """判断链接是否属于付费墙网站"""
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
    """通用RSS抓取函数"""
    items = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "xml")
        # 兼容 item 和 entry 两种格式
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


def fetch_lingowhale():
    items = []
    try:
        res = requests.get("https://lingowhale.com/channels", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a[href]")[:20]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("http" in href or href.startswith("/")):
                url = href if href.startswith("http") else "https://lingowhale.com" + href
                if not is_paywalled(url):
                    items.append({"title": title, "url": url, "source": "LingoWhale"})
    except Exception as e:
        print(f"[LingoWhale] 抓取失败: {e}")
    return items[:10]


def collect_all_content():
    print("开始抓取内容源...")
    all_items = []

    # 一、AI资讯聚合平台
    all_items += fetch_aihot_news()
    all_items += fetch_aihot_events()
    all_items += fetch_bestblogs()
    all_items += fetch_lingowhale()

    # 二、科技媒体
    all_items += fetch_rss("https://techcrunch.com/feed/", "TechCrunch")
    all_items += fetch_rss("https://www.theverge.com/rss/index.xml", "The Verge")
    all_items += fetch_hackernews()

    # 三、中文AI专业媒体
    all_items += fetch_rss("https://36kr.com/feed", "36氪")
    all_items += fetch_rss("https://www.jiqizhixin.com/rss", "机器之心")
    all_items += fetch_rss("https://www.qbitai.com/feed", "量子位")

    # 四、AI企业官方博客
    all_items += fetch_rss("https://www.anthropic.com/news.rss", "Anthropic")
    all_items += fetch_rss("https://openai.com/blog/rss.xml", "OpenAI")
    all_items += fetch_rss("https://blog.google/technology/ai/rss/", "Google AI")

    # 五、AI变现与应用
    all_items += fetch_rss("https://www.producthunt.com/feed", "ProductHunt")
    all_items += fetch_rss("https://www.indiehackers.com/feed.rss", "IndieHackers")

    # 去重
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
# 第二步：DeepSeek AI 过滤+翻译+总结
# ============================================================

def ai_filter_and_summarize(items):
    today = datetime.now().strftime("%Y年%m月%d日")
    raw_text = ""
    for i, item in enumerate(items):
        raw_text += f"{i+1}. [{item['source']}] {item['title']}\n   链接：{item['url']}\n"

    prompt = f"""你是一个专业的AI行业日报编辑。今天是{today}。

以下是从多个来源抓取的原始内容列表，请你完成以下任务：

1. 【筛选】只保留与以下主题相关的内容：
   - AI模型动态（新模型发布、能力更新、评测）
   - AI应用与产品（新产品、功能更新、用户案例）
   - AI赚钱与变现（商业模式、收入案例、创业）
   - AI头部企业动态（OpenAI、Anthropic、Google、Meta、百度、阿里等）
   - AI垂类独角兽（融资、产品、动态）
   - AI优秀实践案例
   - AI学习资源与活动

2. 【翻译】所有英文标题翻译成中文，保持原意，语言自然流畅

3. 【分类输出】按以下格式输出日报，每个分类最多5条，整体不超过20条：

---
📅 AI日报 · {today}
（内容覆盖范围：昨日17:00 - 今日08:00）

🤖 模型与技术
• [标题中文] — 来源：XX
  🔗 链接

📱 应用与产品
• [标题中文] — 来源：XX
  🔗 链接

💰 商业与变现
• [标题中文] — 来源：XX
  🔗 链接

🏢 企业动态
• [标题中文] — 来源：XX
  🔗 链接

🎓 学习与活动
• [标题中文] — 来源：XX
  🔗 链接
---

如果某个分类没有相关内容，跳过该分类不输出。
只输出日报内容，不要有任何多余的说明文字。

原始内容如下：
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
        content = result["choices"][0]["message"]["content"]
        print("AI总结完成")
        return content
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        return None


# ============================================================
# 第三步：推送到飞书群机器人
# ============================================================

def push_via_feishu(report):
    today = datetime.now().strftime("%Y年%m月%d日")
    full_content = f"📬 AI日报 · {today}\n\n{report}\n\n— 由AI日报机器人自动生成"

    if not FEISHU_WEBHOOK:
        raise Exception("FEISHU_WEBHOOK 未配置")

    payload = {
        "msg_type": "text",
        "content": {"text": full_content}
    }
    res = requests.post(FEISHU_WEBHOOK, json=payload, timeout=15).json()

    if res.get("code") == 0:
        print("飞书推送成功！")
    else:
        raise Exception(f"飞书推送失败: {res}")


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

    report = ai_filter_and_summarize(items)
    if not report:
        print("AI总结失败，退出")
        return

    print("\n===== 日报预览 =====")
    print(report)
    print("=" * 50)

    try:
        push_via_feishu(report)
        print("日报推送完成！")
    except Exception as e:
        print(f"推送失败: {e}")


if __name__ == "__main__":
    main()
