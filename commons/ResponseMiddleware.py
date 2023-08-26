from django.middleware.common import CommonMiddleware

class SlackNoRetryMiddleware(CommonMiddleware):
    def process_response(self, request, response):
        if response.status_code != 200:
            response['X-Slack-No-Retry'] = '1'
        return response
