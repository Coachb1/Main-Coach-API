import requests
from tests.helpers import scrape_article_data

API_KEY = 'AIzaSyCbEar5KvvPVTRmm6QrmVmSJSAqylaT_mo'
SEARCH_ENGINE_ID = '74697a1c8338d4d9a'

# search_query = input("Enter your search query: ")

url = 'https://www.googleapis.com/customsearch/v1'

def get_search_links(search_query):
    params = {
        'q': search_query,
        'key': API_KEY,
        'cx': SEARCH_ENGINE_ID
        }

    response = requests.get(url, params=params)
    res = response.json()
    print("Response: ",res)

    if 'items' in res:
        res_links = []
        
        for item in res['items']:
            res_links.append(item['link'])
            
        return res_links


def get_searched_links_contents(search_query, top=1):
    links = get_search_links(search_query)
    print("###################### Links: ",links)
    links_contents = []

    data = ''
    
    processed = 0
    for link in links:
        # print("Link: ",link)
        content = scrape_article_data(link).get('article_content',None)
        if content:
            data += content
            processed += 1
        if processed >= top:
            break
    return data