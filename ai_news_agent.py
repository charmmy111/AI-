import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import os
import random
import time
from datetime import datetime, timedelta

# ================= 1. 配置参数 =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not OPENAI_API_KEY or not WEBHOOK_URL:
    raise ValueError("缺少环境变量！请检查 GitHub Secrets 设置。")

client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.siliconflow.cn/v1") 

RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/", 
    "https://feed.infoq.com/ai-ml-data-eng/news.rss",                
    "https://news.ycombinator.com/rss",                              
]

# 🎯 新增：重点关注的大厂黑话/关键词字典
TARGET_COMPANIES = ["google", "nvidia", "huawei", "openai", "microsoft", "meta", "apple", "deepmind", "anthropic", "xai", "谷歌", "英伟达", "华为", "微软", "苹果"]
# 🎯 新增：代表“被重点引用/重磅发布”的关键词
IMPACT_KEYWORDS = ["paper", "research", "announces", "release", "breakthrough", "sota", "model", "study", "report", "论文", "发布", "开源", "模型", "研究"]


# ================= 2. 核心功能函数 =================

def calculate_weight(title):
    """为文章标题打分，分数越高，被抽中的概率越大"""
    score = 10  # 基础分：每篇文章都有 10 分的底分
    title_lower = title.lower()
    
    # 规则 1：如果包含重点大厂，权重暴增 (+50分)
    for company in TARGET_COMPANIES:
        if company in title_lower:
            score += 50
            break # 命中一个大厂就加分，避免重复加
            
    # 规则 2：如果是研究论文、重磅发布，权重增加 (+40分)
    for kw in IMPACT_KEYWORDS:
        if kw in title_lower:
            score += 40
            break
            
    return score

def get_prioritized_article():
    """获取过去一周的文章，并根据大厂/重磅程度进行加权随机抽选"""
    all_articles = []
    
    # 计算 7 天前的时间戳
    seven_days_ago = datetime.now() - timedelta(days=7)
    seven_days_ago_tuple = seven_days_ago.timetuple()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            # 扩大抓取量到 50 条，以确保能覆盖过去 7 天的内容
            for entry in feed.entries[:50]: 
                
                # 1. 检查文章发布时间
                published_tuple = getattr(entry, 'published_parsed', getattr(entry, 'updated_parsed', None))
                if published_tuple:
                    # 如果文章时间早于 7 天前，直接跳过
                    if published_tuple < seven_days_ago_tuple:
                        continue
                
                # 2. 计算权重得分
                weight = calculate_weight(entry.title)
                
                all_articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "weight": weight
                })
        except Exception as e:
            print(f"解析RSS源 {url} 失败: {e}")
            
    if not all_articles:
        return None
    
    # 🌟 核心：把所有文章的权重提取出来，进行“加权随机抽奖”
    weights_list = [article["weight"] for article in all_articles]
    
    # random.choices 会根据 weights_list 的比例来抽选，k=1 代表抽 1 个
    selected = random.choices(all_articles, weights=weights_list, k=1)[0]
    
    print(f"共搜集到 {len(all_articles)} 篇过去一周的文章。")
    print(f"本次抽中文章权重分: {selected['weight']} (底分10, 命中关键词加分)")
    
    return selected

def scrape_full_text(url):
    """进入该文章的真实网页，爬取完整正文内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = "\n".join([p.get_text() for p in paragraphs])
        return full_text[:8000]
    except Exception as e:
        return f"正文抓取失败: {e}"

def process_with_ai(title, url, content):
    """让大模型对这单篇文章进行视频文案改编"""
    prompt = f"""
    你现在是一位全网拥有百万粉丝的爆款科技视频UP主。你的视频特色是：“能把最硬核、最枯燥的前沿AI大厂论文，用最通俗、幽默的大白话讲给普通观众听”。
    
    今天，我为你抽选了过去一周内的一篇重点科技文章全文。请你仔细阅读正文，把它改编成一期【科普视频的口播文案】。
    
    原文标题：{title}
    原文链接：{url}
    
    以下是爬取到的文章正文：
    ---
    {content}
    ---

    请按照以下 Markdown 格式输出你的视频文案，语气要像面对镜头聊天一样，充满激情、幽默感和互动感：
    
    # 🎬 [起一个吸引眼球、带有悬念的 B站/YouTube 风格爆款标题]
    
    **传送门：** {url}
    
    ### 🎙️ 黄金开场白 (0-15秒)
    (用一个悬念、一个反问，或者一个生活中的痛点，迅速抓住观众的注意力。比如：“哈喽大家好，你敢相信吗...”)
    
    ### 🧠 大白话讲核心 (这到底是个啥？)
    (要求：绝对不许堆砌专业术语！请把你看到的“大模型架构、参数量、算力、Token”等技术黑话，强制翻译成生活中“做菜、建房子、谈恋爱、打游戏”等极其接地气的【比喻】。像讲故事一样娓娓道来。)
    
    ### 🌍 现实杀伤力 (这玩意跟咱们有什么关系？)
    (讲讲这个新发布的技术或文章，到底会怎么改变行业？是会抢掉谁的饭碗？还是能帮普通人赚到钱/省下时间？)
    
    ### 💬 UP主瞎聊与结尾互动
    (用你个人的主观视角吐槽或夸奖一下这件事。最后抛出一个犀利的问题，引导观众在弹幕和评论区留言探讨。)
    """
    
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct", # 根据你使用的平台修改模型名
        messages=[{"role": "user", "content": prompt}],
        # 🌟 重点：将 temperature 调高到 0.7，让大模型发挥更多的想象力和创造力，语气会更幽默活泼
        temperature=0.7 
    )
    return response.choices[0].message.content

def push_notification(markdown_text):
    """推送到飞书/钉钉"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"🤖 本周 AI 重点文献精读 ({datetime.now().strftime('%Y-%m-%d')})\n\n{markdown_text}"
        }
    }
    response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
    print("推送结果:", response.text)

# ================= 3. 主程序运行逻辑 =================
if __name__ == "__main__":
    print("1. 正在检索过去 7 天的新闻，并根据大厂/重磅程度计算权重...")
    article = get_prioritized_article()
    
    if not article:
        print("过去一周未获取到任何文章！")
        exit()
        
    print(f"🎉 抽中文章: {article['title']}")
    print(f"🔗 链接: {article['link']}")
    
    print("2. 正在潜入网页抓取完整正文...")
    full_text = scrape_full_text(article['link'])
    print(f"抓取成功，正文长度: {len(full_text)} 字")
    
    print("3. AI 正在深度阅读并写总结笔记...")
    ai_summary = process_with_ai(article['title'], article['link'], full_text)
    
    print("4. 正在推送...")
    push_notification(ai_summary)
    print("✨ 任务圆满完成！")
