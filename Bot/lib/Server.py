from decimal import *
from icalendar import Calendar

import copy


class Server:

    def __init__(self, json={}):

        if not json:
            json = {}

        self.g_id = int(json.get('g_id', 0))  # id
       
        self.timezone = json.get('timezone', 'UTC')


    def _to_json(self):

        d = dict({'g_id': str(self.g_id), 'timezone': self.timezone})

        return d
