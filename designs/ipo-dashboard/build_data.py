"""Build the prototype's local, source-attributed snapshot; never modify scraper output."""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def clean(s):
    return re.sub(r'\s+', ' ', s).strip()

def fetch(pair):
    source, item = pair
    url = urljoin('https://www.ipokiso.com/', item['detail_url'])
    try:
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        root = soup.select_one('#colum2') if source == 'ipokiso' else (soup.select_one('article') or soup.body)
        for tag in root.select('script, style, nav, .pagenavi, .js-vote, [id^="ad_"], #company_feature, #go'):
            tag.decompose()
        fields = {}
        for tr in root.find_all('tr'):
            cells = tr.find_all(['th','td'], recursive=False)
            if len(cells) == 2 and not cells[1].find('table'):
                fields[clean(cells[0].get_text())] = clean(cells[1].get_text(' ', strip=True))
        comments = []
        for heading in root.find_all(['h2','h3','h4']):
            title = clean(heading.get_text())
            if not re.search('コメント|スタンス|評価', title):
                continue
            chunks = []
            for sibling in heading.next_siblings:
                if getattr(sibling, 'name', None) in ['h2','h3','h4']:
                    break
                if getattr(sibling, 'name', None) in ['script','style']:
                    continue
                s = clean(sibling.get_text(' ', strip=True) if hasattr(sibling, 'get_text') else str(sibling))
                if s:
                    chunks.append(s)
            if chunks:
                comments.append({'title':title, 'text':'\n\n'.join(chunks)})
        docs = [{'title':a.get_text(strip=True),'url':urljoin(url,a['href'])}
                for a in root.find_all('a',href=True) if re.search('目論見書|有価証券届出書', a.get_text())]
        synopsis = root.select_one('.ipo_syno')
        business = clean(synopsis.get_text(' ',strip=True)) if synopsis else ''
        if not business:
            p = root.find('p', string=False)
            for p in root.find_all('p'):
                if '事業内容' in p.get_text():
                    business = clean(p.get_text(' ',strip=True)); break
        website = fields.get('会社URL','')
        if synopsis and synopsis.find('a',href=True):
            website = synopsis.find('a',href=True)['href']
        tables = []
        for table in root.find_all('table'):
            rows = [[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'],recursive=False)]
                    for tr in table.find_all('tr') if tr.find_parent('table') is table]
            if rows and any('売上高' in c for row in rows for c in row) and source == 'ipokiso':
                tables.append(rows)
        return source,item['code'],{'url':url,'fields':fields,'comments':comments,'documents':docs,
                                    'business':business,'website':website,'financials':tables,
                                    'retrieved_at':datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return source,item['code'],{'url':url,'fields':{},'comments':[],'documents':[], 'error':str(exc)}

if __name__ == '__main__':
    a = json.loads((ROOT/'ipo96ut.json').read_text(encoding='utf-8'))
    b = json.loads((ROOT/'ipokiso.json').read_text(encoding='utf-8'))
    companies = {i['code']:{'code':i['code'],'ipo96ut':i} for i in a['items']}
    for i in b['items']:
        companies.setdefault(i['code'], {'code':i['code']})['ipokiso']=i
    jobs = [('ipo96ut',i) for i in a['items']] + [('ipokiso',i) for i in b['items']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for source,code,detail in pool.map(fetch, jobs):
            companies[code][source+'_detail']=detail
            print(source,code,'ERROR' if 'error' in detail else 'OK')
    output={'snapshot_date':a['scraped_at'][:10], 'list_scraped_at':{'ipo96ut':a['scraped_at'],'ipokiso':b['scraped_at']},
            'companies':list(companies.values())}
    (HERE/'data.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    vendor=HERE/'vendor'; vendor.mkdir(exist_ok=True)
    for name,url in [('react.js','https://unpkg.com/react@18.3.1/umd/react.development.js'),
                     ('react-dom.js','https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js'),
                     ('babel.js','https://unpkg.com/@babel/standalone@7.29.0/babel.min.js')]:
        target=vendor/name
        if not target.exists():
            r=requests.get(url,timeout=60); r.raise_for_status(); target.write_bytes(r.content)
