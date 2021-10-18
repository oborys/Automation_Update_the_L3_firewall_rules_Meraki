FROM python:3.9-slim-bullseye
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENV FLASK_APP meraki_automation.py
CMD flask run