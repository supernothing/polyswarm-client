FROM golang:1.9 as builder

WORKDIR /go/src/github.com/awslabs/amazon-ecr-credential-helper

RUN apt-get update -y \
	&& buildDeps=" \
        make \
        gcc \
        g++ \
        git \
        build-essential \
	" \
    && apt-get install -y \
        $buildDeps \
    && git clone https://github.com/awslabs/amazon-ecr-credential-helper.git . \
    && make \
    # cleanup
    && apt-get purge -yqq $buildDeps \
    && apt-get autoremove -yqq \
    && apt-get clean \
    && rm -Rf /tmp/* /var/tmp/* /var/lib/apt/lists/*

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
        unzip \
    && pip3 install --upgrade pip setuptools twine wheel \
    && pip3 install docker-compose tox awscli \
    && rm -rf /tmp/* /var/cache/apk/* \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && mkdir -p /root/.docker \
    && echo " \
    { \
        \"credHelpers\": { \
            \"005789955001.dkr.ecr.us-east-1.amazonaws.com\": \"ecr-login\" \
        } \
    }" > /root/.docker/config.json

COPY --from=builder /go/src/github.com/awslabs/amazon-ecr-credential-helper/bin/local/docker-credential-ecr-login /usr/local/bin/docker-credential-ecr-login

