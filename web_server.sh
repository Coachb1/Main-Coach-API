#!/usr/bin/env bash
./manage.py migrate
./manage.py start_weekly_email_reminder
gunicorn --bind 0.0.0.0:"${WEB_SERVER_PORT:=8000}"\
         --timeout 300 \
         --graceful-timeout 30 \
         --workers 5 \
         --worker-connections 200 \
         --max-requests 5000 \
         --max-requests-jitter 100 \
         wsgi:application