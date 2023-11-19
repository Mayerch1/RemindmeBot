FROM python:3.10.5

WORKDIR /code

RUN apt-get update && apt-get upgrade -y

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt


CMD ["python", "remindmeBot.py"]
