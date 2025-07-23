FROM python:3.11-bookworm as builder

RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libssl3 \             
    libxrender1 \
    fontconfig \
    libjpeg62-turbo \     
    libmemcached-dev \
    zlib1g-dev \
    graphviz \
    graphviz-dev \
    xz-utils


RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bookworm_amd64.deb

RUN dpkg -i wkhtmltox_0.12.6-1.bookworm_amd64.deb || true && \
    apt-get update && \
    apt-get install -y --no-install-recommends -f
RUN rm wkhtmltox_0.12.6-1.bookworm_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
