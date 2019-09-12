FROM lappis/bottis:requirements

COPY ./bot /bot
COPY ./policies /policies/
COPY ./scripts /scripts

WORKDIR /bot


RUN find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf