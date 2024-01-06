import time

import requests


class HTTPHelper:
    """
    A utility class that provides methods for making HTTP requests using the `requests` library.

    Args:
        base_url (str): The base URL used for generating complete URLs.

    Attributes:
        base_url (str): The base URL used for generating complete URLs.
        session (requests.Session): The `requests` session object used for making HTTP requests.
    """

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def get_url(self, endpoint):
        """
        Generates a complete URL by combining the base URL and an endpoint.

        Args:
            endpoint (str): The endpoint to be appended to the base URL.

        Returns:
            str: The complete URL.

        Raises:
            ValueError: If the base URL is invalid.
        """
        if self.base_url is None:
            raise ValueError("invalid BASE_URL")

        base_url = self.base_url.rstrip("/")
        endpoint = endpoint.strip("/")

        return f"{base_url}/{endpoint}"

    def request(self, method, url, retries=1, backoff=1, **kwargs):
        """
        Makes an HTTP request with the specified method, URL, and optional parameters.
        Handles retries and backoff for failed requests.

        Args:
            method (str): The HTTP method to be used for the request.
            url (str): The URL to send the request to.
            retries (int, optional): The number of retries to attempt for failed requests. Defaults to 1.
            backoff (int, optional): The backoff time between retries in seconds. Defaults to 1.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.

        Raises:
            requests.exceptions.RequestException: If the request fails after all retries.
        """
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
        """
        Makes a GET request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.
        """
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        """
        Makes a POST request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.
        """
        return self.request('POST', url, **kwargs)

    def patch(self, url, **kwargs):
        """
        Makes a PATCH request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.
        """
        return self.request('PATCH', url, **kwargs)

    def put(self, url, **kwargs):
        """
        Makes a PUT request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.
        """
        return self.request('PUT', url, **kwargs)

    def delete(self, url, **kwargs):
        """
        Makes a DELETE request to the specified URL.

        Args:
            url (str): The URL to send the request to.
            **kwargs: Additional keyword arguments to be passed to the `requests` library.

        Returns:
            requests.Response: The response object.
        """
        return self.request('DELETE', url, **kwargs)
