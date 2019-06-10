FROM docker:stable
# This image has python 3.6.8 and our common dependencies used to run CI builds.
RUN apk --no-cache add \
        curl \
        git \
        gcc \
        jq \
        libffi-dev \
        make \
        musl-dev \
        openssl-dev \
        py3-pip \
        py3-requests \
        python3-dev \
        unzip && \
    pip3 install --upgrade pip setuptools twine wheel && \
    pip3 install docker-compose tox awscli
RUN ln -s /usr/bin/python3 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip
