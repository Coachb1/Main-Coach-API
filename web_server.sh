#!/usr/bin/env bash
./manage.py migrate
curl -Ls https://download.newrelic.com/install/newrelic-cli/scripts/install.sh | bash && sudo NEW_RELIC_API_KEY=NRAK-OK6LYI5AERXPXO4XHOQSNY0DUFL NEW_RELIC_ACCOUNT_ID=4088629 /usr/local/bin/newrelic install -n logs-integration
newrelic-admin run-python gunicorn --bind 0.0.0.0:"${WEB_SERVER_PORT:=8000}"\
         --timeout 120 \
         --graceful-timeout 30 \
         --workers 5 \
         --worker-connections 200 \
         --max-requests 5000 \
         --max-requests-jitter 100 \
         wsgi:application