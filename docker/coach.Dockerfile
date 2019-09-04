FROM lappis/botrequirements:boilerplate

COPY ./coach /coach
COPY ./scripts /scripts
COPY ./policies /coach/policies/

RUN mkdir /src_models

WORKDIR /coach

RUN make train

RUN find /. | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
