import feedparser
from openai import OpenAI
import requests
import json
import os
from datetime import datetime

# 1. 配置参数 (改为从环境变量读取)
# 这样写的意思是：去系统中寻找叫 OPENAI_API_KEY 的变量
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 检查一下有没有成功读取到，如果没有，程序报错提醒
if not OPENAI_API_KEY or not WEBHOOK_URL:
    raise ValueError("缺少 API_KEY 或 WEBHOOK_URL 环境变量！请检查 GitHub Secrets 设置。")

client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.siliconflow.cn/v1")

# 订阅的RSS源列表
RSS_FEEDS = [
    "https://news.ycombinator.com/rss",  # Hacker News
    # 可以添加更多关于AI的RSS源
]


def fetch_news():
    """从RSS源获取今日新闻"""
    today_news = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        # 只取前15条，避免超过大模型上下文限制
        for entry in feed.entries[:15]:
            today_news.append(f"标题: {entry.title}\n链接: {entry.link}\n摘要: {entry.get('description', '无')}\n")
    return "\n---\n".join(today_news)


def process_with_ai(news_text):
    """让大模型筛选并总结AI新闻"""
    prompt = f"""
    你是一个资深的AI前沿科技编辑。请阅读以下从科技媒体抓取的原始新闻列表。
    你的任务是：
    1. 严格筛选出只与"人工智能(AI)、大模型、机器学习、前沿科技"相关的新闻，忽略无关内容。
    2. 将筛选出的新闻翻译并总结为中文。
    3. 输出格式要求为Markdown：
       - 使用 Emoji 增加可读性
       - 包含：新闻标题、一句话核心看点、原文链接
       - 如果今天没有AI相关的重大新闻，请回复“今日暂无重大AI前沿新闻”。

    以下是原始新闻：
    {news_text}
    """

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",  # 根据你使用的API替换模型名字
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3  # 保持输出的稳定性
    )
    return response.choices[0].message.content


def push_notification(markdown_text):
    """推送到飞书/钉钉 (这里以飞书为例)"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"🤖 今日AI前沿早报 ({datetime.now().strftime('%Y-%m-%d')})\n\n{markdown_text}"
        }
    }
    response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
    print("推送结果:", response.text)


if __name__ == "__main__":
    print("1. 正在抓取新闻...")
    raw_news = fetch_news()

    print("2. AI正在筛选和总结...")
    ai_summary = process_with_ai(raw_news)

    print("3. 正在推送...")
    push_notification(ai_summary)
    print("完成！")
