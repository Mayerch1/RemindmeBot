import os

import pymongo
from pymongo import MongoClient

from lib import Reminder
from lib.Reminder import Reminder


class Analytics:

    client = None
    db = None

    @staticmethod
    def init():
        host = os.getenv('MONGO_ANALYTICS_CONN')
        port = int(os.getenv('MONGO_ANALYTICS_PORT'))

        uname = os.getenv('MONGO_ANALYTICS_USER')
        pw = os.getenv('MONGO_ANALYTICS_PASS')

        Analytics.client = MongoClient(host=host, username=uname, password=pw, port=port)
        Analytics.db = Analytics.client.analytics


    @staticmethod
    def delete_guild(guild_id: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'removed_gs': 1}}, new=True, upsert=True)

    @staticmethod
    def add_guild(guild_id: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'added_gs': 1}}, new=True, upsert=True)


    @staticmethod
    def add_self_reminder(rem: Reminder):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'self_reminders': 1}}, new=True, upsert=True)
        Analytics.reminder_stats(rem)


    @staticmethod
    def add_foreign_reminder(rem: Reminder):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'f_reminders': 1}}, new=True, upsert=True)
        Analytics.reminder_stats(rem)
        

    @staticmethod
    def convert_to_interval():
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'to_interval_conv': 1}}, new=True, upsert=True)


    @staticmethod
    def convert_to_reminder():
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'to_reminder_conv': 1}}, new=True, upsert=True)

    @staticmethod
    def delete_orphans(count: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'deleted_orphans': count}}, new=True, upsert=True)

    @staticmethod
    def add_ruleset():
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'rules_added': 1}}, new=True, upsert=True)

    @staticmethod
    def rm_ruleset():
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'rules_removed': 1}}, new=True, upsert=True)


    @staticmethod
    def reminder_stats(rem: Reminder):

        # add this before avg calculation
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'reminders': 1}}, new=True, upsert=True)

        delta = rem.at - rem.created_at
        delta = delta.seconds

        Analytics.db.deltas.find_one_and_update({'g_id': '0'}, {'$min': {'min_delta': delta}}, new=True, upsert=True)
        Analytics.db.deltas.find_one_and_update({'g_id': '0'}, {'$max': {'max_delta': delta}}, new=True, upsert=True)


        # avg calculation is a bit harder, as it requires existing data
        query = Analytics.db.counts.find_one({'g_id': '0'}, {'reminders': 1})
        rem_cnt = query.get('reminders', 1) # this reminder was already added in statement above

        query = Analytics.db.deltas.find_one({'g_id': '0'}, {'avg_delta': 1})
        avg_delta = query.get('avg_delta', 0)

        if avg_delta == 0:
            avg_delta = delta # avg_delta recording is missing, assume this is the first
        else:
            avg_delta = avg_delta/rem_cnt + delta/rem_cnt
        
        Analytics.db.deltas.find_one_and_update({'g_id': '0'}, {'$set': {'avg_delta': avg_delta}}, new=True, upsert=True)


    @staticmethod
    def delete_reminder():
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'deleted_reminders': 1}}, new=True, upsert=True)

    @staticmethod
    def invalid_f_string():
       Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$inc': {'invalid_format': 1}}, new=True, upsert=True) 

    @staticmethod
    def current_guilds(guild_cnt: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$set': {'guild_count': guild_cnt}}, new=True, upsert=True) 

    @staticmethod
    def active_reminders(rem_cnt: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$set': {'active_reminders': rem_cnt}}, new=True, upsert=True)

    @staticmethod
    def active_intervals(intvl_cnt: int):
        Analytics.db.counts.find_one_and_update({'g_id': '0'}, {'$set': {'active_intervals': intvl_cnt}}, new=True, upsert=True)