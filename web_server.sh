#!/usr/bin/env bash

echo "Started"

echo "New Relic CLI installation"
#Installing New Relic CLI
vers=$(newrelic --version)
echo "$vers"
echo "New Relic CLI Finished"

# Getting New Relic Key
env_file=".env"
key="NEW_RELIC_KEY"
value=$(grep -w "$key" "$env_file" | cut -d '=' -f 2 | sed 's/^"//' | sed 's/"$//' | tr -d '"')


echo "New Relic File getting Created"
#generating config file
newrelic-admin generate-config $value newrelic.ini

cat newrelic.ini

# Command to run server
echo "Server Getting Started"
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program gunicorn --bind 0.0.0.0:"${WEB_SERVER_PORT:=8000}"\
         --timeout 60 \
         --graceful-timeout 30 \
         --workers 5 \
         --worker-connections 200 \
         --max-requests 5000 \
         --max-requests-jitter 100 \
         wsgi:application