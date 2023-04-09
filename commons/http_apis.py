import time

import requests


class HTTPHelper:

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def get_url(self, endpoint):
        if self.base_url is None:
            raise ValueError("invalid BASE_URL")

        base_url = self.base_url.rstrip("/")
        endpoint = endpoint.strip("/")

        return f"{base_url}/{endpoint}"

    def request(self, method, url, retries=1, backoff=1, **kwargs):
        while retries > 0:
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                retries -= 1
                if retries == 0:
                    raise e
                else:
                    time.sleep(backoff * (retries - retries))

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request('PATCH', url, **kwargs)

    def put(self, url, **kwargs):
        return self.request('PUT', url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)
