import requests
from bs4 import BeautifulSoup
from config import ANNA_SEARCH, GEMINI_URL, GEMINI_API_KEY
import json

# ---------------------------
# استخدام Gemini API لمعالجة النصوص
# ---------------------------
def analyze_content_with_gemini(prompt: str) -> str:
    """
    يرسل نص إلى Gemini API ويستخرج محتوى محسّن أو منسّق
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    payload = {
        "prompt": prompt,
        "temperature": 0.7,
        "max_output_tokens": 500
    }
    try:
        resp = requests.post(GEMINI_URL, headers=headers, data=json.dumps(payload), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # استخراج النص الناتج
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0].get("content", "")
        return ""
    except Exception as e:
        print("Gemini API error:", e)
        return ""

# ---------------------------
# البحث في Anna’s Archive
# ---------------------------
def search_books(query: str, page: int = 1) -> list:
    """
    البحث عن الكتب على موقع Anna's Archive
    يعيد قائمة كتب: [{title, cover, description, slow_links:[(label, url)]}]
    """
    url = f"{ANNA_SEARCH}{query}&page={page}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MRClassicBot/1.0)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for item in soup.select("div.book-item"):  # تعديل حسب الهيكل الحقيقي للموقع
            title = item.select_one("h3.book-title").text.strip() if item.select_one("h3.book-title") else "لا يوجد عنوان"
            cover = item.select_one("img.book-cover")["src"] if item.select_one("img.book-cover") else None
            description_raw = item.select_one("div.book-description").text.strip() if item.select_one("div.book-description") else ""
            description = analyze_content_with_gemini(description_raw)

            slow_links = []
            for idx, link in enumerate(item.select("a.slow-download")):  # الروابط البطيئة
                label = f"رابط {idx+1}"
                slow_links.append((label, link.get("href")))

            results.append({
                "title": title,
                "cover": cover,
                "description": description,
                "slow_links": slow_links
            })
        return results
    except Exception as e:
        print("Search error:", e)
        return []
