import requests
import pytz
import sys
import hmac
import hashlib
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def get_h(sid):
        def HMAC_SHA256(private_key="", message="", time=""):
            message += ":"

            if time:
                message += str(time)
            else:
                message += str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

            return hmac.new(str.encode(private_key), str.encode(message), hashlib.sha256).hexdigest()

        private_key = os.getenv('JOTURL_PRIVATE_KEY')
        gmt_datetime = str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

        return str(HMAC_SHA256(private_key, sid, gmt_datetime))

def get_pass_for_sid():
    try:
        def HMAC_SHA256(private_key="", message="", time=""):
            message += ":"

            if time:
                message += str(time)
            else:
                message += str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

            return hmac.new(str.encode(private_key), str.encode(message), hashlib.sha256).hexdigest()


        public_key = os.getenv("JOTURL_PUBLIC_KEY")
        private_key = os.getenv("JOTURL_PRIVATE_KEY")
        gmt_datetime = str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))


        return HMAC_SHA256(private_key, public_key, gmt_datetime)

    except Exception as e:
        print(e)
        sys.exit(0)


def get_sid(email):
    password = get_pass_for_sid()
    url = f"https://joturl.com/a/i1/users/login?username={email}&password={password}"
    resp = requests.get(url)
    res = resp.json()
    session_id = res['result']['session_id']
    return session_id
