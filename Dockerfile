FROM dxflrs/garage:v2.1.0 AS garage

FROM alpine:3.20
COPY --from=garage /garage /usr/local/bin/garage
COPY garage.toml /etc/garage.toml
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 3900 3902 3903
CMD ["/usr/local/bin/entrypoint.sh"]