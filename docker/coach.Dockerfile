FROM lappis/bottis_requirements:latest

COPY ./coach /coach
COPY ./scripts /scripts
COPY ./policies /policies/

RUN mv ./coach/base_config/nginx.conf /etc/nginx/conf.d/nginx.conf
RUN mv ./coach/base_config/* /

RUN mkdir /src_models

RUN make train

RUN ./compress_models.sh

RUN find /. | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf

CMD ["nginx", "-g", "daemon off;"]