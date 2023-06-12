from commons.timeit import timeit
from url_shortener.models import UrlShortenerMap


@timeit
def chech_url_exists(long_url_hash, tenant_id):
    # check whether an entry with the given conditions exists and if exists then return the short url
    try:
        url_map = UrlShortenerMap.objects.get(
            long_url_hash=long_url_hash, tenant_id=tenant_id)
        return url_map.short_url
    except UrlShortenerMap.DoesNotExist:
        return None
