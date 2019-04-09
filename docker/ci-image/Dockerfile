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
    pip3 install docker-compose tox && \
    curl https://releases.hashicorp.com/packer/1.3.1/packer_1.3.1_linux_amd64.zip > packer.zip && \
    unzip -d /usr/bin/ packer.zip && \
    rm -f packer.zip