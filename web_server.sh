#!/usr/bin/env bash
./manage.py migrate
gunicorn --bind 0.0.0.0:"${WEB_SERVER_PORT:=8000}"\
         --timeout 120 \
         --graceful-timeout 30 \
         --workers 5 \
         --worker-connections 200 \
         --max-requests 5000 \
         --max-requests-jitter 100 \
         wsgi:application