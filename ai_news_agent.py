import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import os
import random
from datetime import datetime

# ================= 1. 配置参数 =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not OPENAI_API_KEY or not WEBHOOK_URL:
    raise ValueError("缺少环境变量！请检查 GitHub Secrets 设置。")

# 请根据你使用的平台（硅基流动或谷歌）修改 base_url
client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.siliconflow.cn/v1") 

# 高质量 AI 新闻源
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/", 
    "https://feed.infoq.com/ai-ml-data-eng/news.rss",                
    "https://news.ycombinator.com/rss",                              
]

# ================= 2. 核心功能函数 =================

def get_random_article():
    """从所有新闻源中获取所有文章列表，并随机挑选一篇"""
    all_articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]: 
                all_articles.append({
                    "title": entry.title,
                    "link": entry.link
                })
        except Exception as e:
            print(f"解析RSS源 {url} 失败: {e}")
            
    if not all_articles:
        return None
    
    # 🌟 核心：从总池子中随机抽选 1 篇
    selected = random.choice(all_articles)
    return selected

def scrape_full_text(url):
    """进入该文章的真实网页，爬取完整正文内容"""
    # 伪装成真实的浏览器访问，防止被网站拦截
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # 使用 BeautifulSoup 解析网页 HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取网页中所有的 <p> 标签（通常是文章正文段落）
        paragraphs = soup.find_all('p')
        full_text = "\n".join([p.get_text() for p in paragraphs])
        
        # 如果文章太长，只取前 8000 字，避免超过大模型限制
        return full_text[:8000]
    except Exception as e:
        return f"正文抓取失败: {e}"

def process_with_ai(title, url, content):
    """让大模型对这单篇文章进行深度总结"""
    prompt = f"""
    你是一个资深的AI前沿科技研究员。我为你随机抽取了今天的一篇外网科技文章全文。
    请你仔细阅读正文，写一篇结构清晰的【深度中文总结笔记】。
    
    原文标题：{title}
    原文链接：{url}
    
    以下是爬取到的文章正文：
    ---
    {content}
    ---

    请按照以下 Markdown 格式输出你的总结（排版要精美）：
    
    # 📌 [将原标题翻译成恰当的中文]
    
    **原文链接：** {url}
    
    ### 📖 核心摘要 (用精炼的一两句话概括这篇文章讲了什么核心事情)
    ...
    
    ### 💡 深度解析 (根据正文，分点列出3-4个核心细节、技术重点或行业影响)
    - ...
    - ...
    - ...
    
    ### 🧠 研究员短评 (用你专业的视角，用一段话点评一下这件事的意义)
    ...
    """
    
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct", # 根据你使用的平台修改模型名
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4 
    )
    return response.choices[0].message.content

def push_notification(markdown_text):
    """推送到飞书/钉钉"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": {
            # 确保这里包含了你机器人的关键词（例如"早报"、"AI"）
            "text": f"🤖 每日 AI 深度随机抽读 ({datetime.now().strftime('%Y-%m-%d')})\n\n{markdown_text}"
        }
    }
    response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
    print("推送结果:", response.text)

# ================= 3. 主程序运行逻辑 =================
if __name__ == "__main__":
    print("1. 正在从各大源汇总新闻并随机抽选...")
    article = get_random_article()
    
    if not article:
        print("未获取到任何文章！")
        exit()
        
    print(f"抽中文章: {article['title']}")
    print(f"链接: {article['link']}")
    
    print("2. 正在潜入网页抓取完整正文...")
    full_text = scrape_full_text(article['link'])
    print(f"抓取成功，正文长度: {len(full_text)} 字")
    
    print("3. AI 正在深度阅读并写总结笔记...")
    ai_summary = process_with_ai(article['title'], article['link'], full_text)
    
    print("4. 正在推送...")
    push_notification(ai_summary)
