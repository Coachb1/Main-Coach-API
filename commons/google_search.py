import requests
from tests.helpers import scrape_article_data

API_KEY = 'AIzaSyCbEar5KvvPVTRmm6QrmVmSJSAqylaT_mo'
SEARCH_ENGINE_ID = '74697a1c8338d4d9a'

# search_query = input("Enter your search query: ")

url = 'https://www.googleapis.com/customsearch/v1'

def get_search_links(search_query):
    """
    Get the search links for a given search query.

    Parameters:
    - search_query (str): The search query to be used.
        
    Returns:
    - res_links (list): A list of search links.

    Example:
    get_search_links('python tutorials')
    response: ['https://www.python.org/', 'https://realpython.com/', 'https://www.tutorialspoint.com/python/index.htm']
    """
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
    """
    Fetches the contents of the top 'n' search results for a given search query.

    Parameters:
    - search_query (str): The search query to be used.
    - top (int): The number of top search results to fetch. Default is 1.

    Returns:
    - data (str): The concatenated contents of the top 'n' search results.

    Example:
    get_searched_links_contents('python tutorials', 2)
    response: 'Python is a high-level, interpreted programming language...'
    """
    # Get the search links for the given query
    links = get_search_links(search_query)
    print("###################### Links: ",links)
    links_contents = []

    data = ''
    
    processed = 0
    for link in links:
        # Scrape the article data from the link
        content = scrape_article_data(link).get('article_content',None)
        # If the content exists, add it to the data
        if content:
            data += content
            processed += 1
        # If we have processed the top 'n' links, break the loop
        if processed >= top:
            break
    return data