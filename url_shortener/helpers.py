from commons.timeit import timeit
from url_shortener.models import UrlShortenerMap
import requests
import json
import settings


@timeit
def check_url_exists(long_url_hash, tenant_id):
    # check whether an entry with the given conditions exists and if exists then return the short url
    try:
        url_map = UrlShortenerMap.objects.get(
            long_url_hash=long_url_hash, tenant_id=tenant_id)
        return url_map.short_url
    except UrlShortenerMap.DoesNotExist:
        return None


def url_shortify(long_url):
    # print('--'*100)
    # print('Inside url_shortify')
    # print(f'long_url: {long_url}')
    API_KEY = settings.URL_SHORTENING_API_KEY

    linkRequest = {
        "destination": long_url, "domain": {"fullName": "rebrand.ly"}
        # , "slashtag": "A_NEW_SLASHTAG"
    }

    requestHeaders = {
        "Content-type": "application/json",
        "apikey": API_KEY,
    }

    # print('--'*100)
    # print('Before making request to rebrandly')

    r = requests.post("https://api.rebrandly.com/v1/links",
                      data=json.dumps(linkRequest),
                      headers=requestHeaders)

    # print('--'*100)
    # print('After making request to rebrandly')
    # print(f'r.status_code: {r.status_code}')
    # print(f'r.json(): {r.json()}')

    if (r.status_code == requests.codes.ok):
        link = r.json()
        short_url = link["shortUrl"]

        return short_url
