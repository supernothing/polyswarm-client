FROM docker:stable

RUN apk --no-cache add curl jq unzip py3-pip && \
    pip3 install --upgrade pip && \
    pip3 install docker-compose wheel && \
    curl https://releases.hashicorp.com/packer/1.3.5/packer_1.3.5_linux_amd64.zip > packer.zip && \
    unzip -d /usr/bin/ packer.zip && \
    rm -f packer.zip