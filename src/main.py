import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ============================================================
# 配置（从环境变量读取，不要直接填在这里）
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
WX_APP_ID = os.environ.get("WX_APP_ID")
WX_APP_SECRET = os.environ.get("WX_APP_SECRET")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# 第一步：抓取各内容源
# ============================================================

def fetch_aihot_news():
    """抓取 aihot.today AI新闻"""
    items = []
    try:
        res = requests.get("https://aihot.today/ai-news", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a[href]")[:30]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("http" in href or href.startswith("/")):
                url = href if href.startswith("http") else "https://aihot.today" + href
                items.append({"title": title, "url": url, "source": "aihot新闻"})
    except Exception as e:
        print(f"[aihot新闻] 抓取失败: {e}")
    return items[:15]


def fetch_aihot_events():
    """抓取 aihot.today AI活动"""
    items = []
    try:
        res = requests.get("https://aihot.today/ai-event", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a[href]")[:20]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if len(title) > 10 and ("http" in href or href.startswith("/")):
                url = href if href.startswith("http") else "https://aihot.today" + href
                items.append({"title": title, "url": url, "source": "aihot活动"})
    except Exception as e:
        print(f"[aihot活动] 抓取失败: {e}")
    return items[:10]


def fetch_bestblogs():
    """抓取 bestblogs.dev 精选文章"""
    items = []
    urls = [
        ("https://www.bestblogs.dev/articles", "精选文章"),
        ("https://www.bestblogs.dev/videos",   "精选视频"),
        ("https://www.bestblogs.dev/tweets",   "精选推文"),
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
                    items.append({"title": title, "url": full_url, "source": label})
        except Exception as e:
            print(f"[bestblogs {label}] 抓取失败: {e}")
    return items[:20]


def fetch_techcrunch():
    """抓取 TechCrunch RSS"""
    items = []
    try:
        res = requests.get("https://techcrunch.com/feed/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "xml")
        for item in soup.select("item")[:20]:
            title = item.find("title")
            link = item.find("link")
            if title and link:
                items.append({
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True),
                    "source": "TechCrunch"
                })
    except Exception as e:
        print(f"[TechCrunch] 抓取失败: {e}")
    return items[:15]


def fetch_theverge():
    """抓取 The Verge RSS"""
    items = []
    try:
        res = requests.get("https://www.theverge.com/rss/index.xml", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "xml")
        for entry in soup.select("entry")[:20]:
            title = entry.find("title")
            link = entry.find("link")
            if title and link:
                items.append({
                    "title": title.get_text(strip=True),
                    "url": link.get("href", ""),
                    "source": "The Verge"
                })
    except Exception as e:
        print(f"[The Verge] 抓取失败: {e}")
    return items[:15]


def fetch_hackernews():
    """抓取 Hacker News AI相关"""
    items = []
    try:
        res = requests.get("https://hacker-news.firebaseio.com/v0/newstories.json", timeout=10)
        story_ids = res.json()[:50]
        for sid in story_ids[:30]:
            story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
            if story and story.get("title"):
                title = story.get("title", "")
                url = story.get("url", f"https://news.ycombinator.com/item?id={sid}")
                items.append({"title": title, "url": url, "source": "Hacker News"})
    except Exception as e:
        print(f"[Hacker News] 抓取失败: {e}")
    return items[:20]


def collect_all_content():
    """汇总所有内容源"""
    print("开始抓取内容源...")
    all_items = []
    all_items += fetch_aihot_news()
    all_items += fetch_aihot_events()
    all_items += fetch_bestblogs()
    all_items += fetch_techcrunch()
    all_items += fetch_theverge()
    all_items += fetch_hackernews()

    # 去重（按标题）
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"共抓取 {len(unique)} 条原始内容")
    return unique


# ============================================================
# 第二步：DeepSeek AI 过滤+翻译+总结
# ============================================================

def ai_filter_and_summarize(items):
    """用 DeepSeek 过滤AI相关内容并生成中文日报"""

    today = datetime.now().strftime("%Y年%m月%d日")

    # 把所有条目整理成文本
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
# 第三步：通过腾讯云函数中转推送微信（固定IP，无白名单问题）
# ============================================================

SCF_URL = os.environ.get("SCF_URL", "")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "")


def push_via_scf(report):
    """把日报发给腾讯云函数，由云函数负责推送微信"""
    today = datetime.now().strftime("%Y年%m月%d日")
    full_content = f"📬 AI日报 · {today}\n\n{report}\n\n— 由AI日报机器人自动生成"

    if not SCF_URL:
        raise Exception("SCF_URL 未配置，请在 GitHub Secrets 中添加")

    payload = {
        "token": SECRET_TOKEN,
        "content": full_content
    }
    res = requests.post(SCF_URL, json=payload, timeout=30)
    result = res.json()

    if result.get("ok"):
        print(f"推送成功！共发送给 {result.get('sent', 0)} 人")
    else:
        raise Exception(f"云函数返回错误: {result}")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 50)
    print(f"AI日报开始运行：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 抓取内容
    items = collect_all_content()
    if not items:
        print("未抓取到任何内容，退出")
        return

    # 2. AI过滤+总结
    report = ai_filter_and_summarize(items)
    if not report:
        print("AI总结失败，退出")
        return

    print("\n===== 日报预览 =====")
    print(report)
    print("=" * 50)

    # 3. 通过腾讯云函数推送微信
    try:
        push_via_scf(report)
        print("日报推送完成！")
    except Exception as e:
        print(f"推送失败: {e}")
        print("请检查 SCF_URL 和 SECRET_TOKEN 是否正确配置")


if __name__ == "__main__":
    main()
