FROM python:3.9.2

RUN apt-get update && apt-get upgrade -y

RUN pip3 install discord.py discord-py-interactions pytz tzdata PyNaCl python-dateutil pymongo requests Unidecode prometheus-client waitress Flask recurrent parsedatetime

WORKDIR /code
CMD ["python", "remindmeBot.py"]
