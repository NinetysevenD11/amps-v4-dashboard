#!/usr/bin/env python3
"""
app.py의 fetch_macro_news 함수를 미국 뉴스 전용으로 교체합니다.
사용법: app.py와 같은 폴더에서 python patch_news.py
"""
import re, shutil

FILE = "app.py"
shutil.copy(FILE, FILE + ".bak_news")

with open(FILE, "r", encoding="utf-8") as f:
    code = f.read()

# 정규식으로 함수 전체를 찾아서 교체
# @st.cache_data(ttl=900) 또는 ttl=아무숫자
# def fetch_macro_news(): 로 시작
# return headlines_for_ai, news_items 로 끝나는 블록
pattern = r'@st\.cache_data\(ttl=\d+\)\ndef fetch_macro_news\(\):.*?return headlines_for_ai, news_items'

new_func = '''@st.cache_data(ttl=1800)
def fetch_macro_news():
    headlines_for_ai, news_items = [], []
    queries = [
        "Wall Street stock market",
        "Federal Reserve interest rate",
        "S&P 500 Nasdaq earnings",
    ]
    seen_titles = set()
    for q in queries:
        try:
            search_query = urllib.parse.quote(q)
            url = f"https://news.google.com/rss/search?q={search_query}+when:1d&hl=en&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=8).read())
            for item in root.findall('.//item')[:6]:
                t = item.find('title').text
                l = item.find('link').text
                d = item.find('pubDate').text
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    headlines_for_ai.append(t)
                    news_items.append({"title": t, "link": l, "date": d[:-4]})
        except:
            pass
    return headlines_for_ai[:15], news_items[:15]'''

result, count = re.subn(pattern, new_func, code, flags=re.DOTALL)

if count > 0:
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"✅ 완료! fetch_macro_news 교체됨 ({count}곳)")
    print(f"📦 백업: {FILE}.bak_news")
else:
    print("❌ fetch_macro_news 함수를 찾지 못했습니다.")
    print("   app.py 파일이 같은 폴더에 있는지 확인하세요.")
