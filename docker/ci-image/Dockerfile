FROM docker:stable

RUN apk --no-cache add curl jq unzip py3-pip gcc python3-dev musl-dev libffi-dev openssl-dev make && \
    pip3 install --upgrade pip && \
    pip3 install docker-compose wheel && \
    curl https://releases.hashicorp.com/packer/1.3.1/packer_1.3.1_linux_amd64.zip > packer.zip && \
    unzip -d /usr/bin/ packer.zip && \
    rm -f packer.zip