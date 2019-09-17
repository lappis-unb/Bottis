FROM lappis/bottis-requirements:latest

COPY ./bot /bot
COPY ./policies /policies/
COPY ./scripts /scripts

RUN cp /bot/Makefile /Makefile

RUN find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf