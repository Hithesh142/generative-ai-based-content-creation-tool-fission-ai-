import requests
from bs4 import BeautifulSoup
import re

OLLAMA_URL = "http://localhost:11434/api/generate"

def extract_keywords(text):
    prompt = f"""Extract 5 to 10 important keywords or keyphrases from the following text, in a comma-separated list:
    
{text}

Keywords:"""

    data = {
        "model": "gemma3:1b",
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=data)
    result = response.json()
    keywords = result.get("response", "").strip()
    
    return [kw.strip() for kw in re.split(r',\s*', keywords)]


def search_web_articles(keywords, num_results=3):
    from duckduckgo_search import DDGS  # Use DuckDuckGo API for free search
    
    query = " ".join(keywords)
    results = []
    
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=num_results):
            results.append(r["href"])
    
    return results


def fetch_article_text(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([p.get_text() for p in paragraphs])
        return content.strip()
    except Exception as e:
        return ""
