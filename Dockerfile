FROM python:3.14
RUN mkdir /opt/microphone
COPY LICENSE /opt/microphone/
COPY common.py /opt/microphone/
COPY db.py /opt/microphone/
COPY fetch.py /opt/microphone/
COPY frames.py /opt/microphone/
COPY mp3.py /opt/microphone/
COPY server.py /opt/microphone/
COPY ad_database.json.gz /opt/microphone/

ENTRYPOINT ["python", "/opt/microphone/server.py"]

# Make sure to set MICROPHONE_TOKEN for auth

# Docker really wants to use IPv4 for containers
ENV MICROPHONE_ADDRESS 0.0.0.0
ENV MICROPHONE_PORT 8080
ENV MICROPHONE_DATABASE_PATH /opt/microphone/ad_database.json.gz
EXPOSE 8080

