FROM lappis/bottis:coach as coach
FROM lappis/bottis:requirements


COPY ./bot /bot
COPY ./scripts /scripts
COPY --from=coach /src_models/ /models/

WORKDIR /bot


RUN find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf