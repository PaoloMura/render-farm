#FROM python:3.8-slim-buster
FROM blendergrid/blender

WORKDIR /app

RUN apt-get -y update
RUN apt-get -y install ffmpeg
RUN apt-get -y install python3 -y
RUN apt-get -y install python3-pip

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

ENV AWS_ACCESS_KEY_ID=""
ENV AWS_SECRET_ACCESS_KEY=""

CMD [ "python3", "worker.py" ]