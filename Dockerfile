FROM python:3.11-bookworm as builder

RUN apt-get update

RUN apt-get install -y build-essential libssl-dev libxrender-dev wget gdebi
RUN apt-get install -y libmemcached-dev zlib1g-dev

RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb

RUN gdebi --n wkhtmltox_0.12.6-1.buster_amd64.deb

RUN apt-get install -y graphviz graphviz-dev

ENV PYTHONUNBUFFERED 1

RUN mkdir /code

WORKDIR /code/

ENV VIRTUAL_ENV=/opt/venv

RUN python3 -m venv $VIRTUAL_ENV

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install wheel

ADD requirements.txt /code/requirements.txt

RUN pip install -r requirements.txt

ADD . /code/

EXPOSE 8000

RUN chmod +x /code/web_server.sh

CMD ["/code/web_server.sh"]
