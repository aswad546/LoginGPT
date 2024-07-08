FROM jupyter/minimal-notebook:python-3.10

EXPOSE 8888
ENV debian_frontend=noninteractive
ENV GRANT_SUDO=yes
USER root

# install dependencies
RUN apt update
RUN apt upgrade -y
RUN apt install -y curl tar tmux graphviz psmisc htop git

# install https://code.visualstudio.com/docs/remote/tunnels
RUN curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output /tmp/vscode_cli.tar.gz
RUN tar -xf /tmp/vscode_cli.tar.gz -C /usr/local/bin

COPY startup.sh /startup.sh
RUN chmod +x /startup.sh
ENTRYPOINT [ "/startup.sh" ]
