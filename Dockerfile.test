FROM themattrix/tox-base

MAINTAINER Mike McCoy michael.b.mccoy@gmail.com

COPY install-prereqs*.sh requirements*.txt tox.ini /app/
COPY vendor /app/vendor
ARG SKIP_TOX=true
RUN bash -c " \
    if [ -f '/app/install-prereqs.sh' ]; then \
        bash /app/install-prereqs.sh; \
    fi && \
    if [ $SKIP_TOX == false ]; then \
        TOXBUILD=true tox; \
    fi"
