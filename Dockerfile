FROM python:3

RUN apt-get update && apt-get -y install ffmpeg

RUN pip3 install discord.py discord-py-slash-command pytz tzdata PyNaCl python-dateutil pymongo requests

WORKDIR /code
CMD ["python", "remindmeBot.py"]
