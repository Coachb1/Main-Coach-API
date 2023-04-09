FROM python:3.11-buster

ENV PYTHONUNBUFFERED 1

RUN mkdir /code

WORKDIR /code/

ENV VIRTUAL_ENV=/opt/venv

RUN python3 -m venv $VIRTUAL_ENV

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip

ADD requirements.txt /code/requirements.txt

RUN pip install -r requirements.txt

ADD . /code/

EXPOSE 8000

RUN chmod +x /code/web_server.sh

CMD ["/code/web_server.sh"]