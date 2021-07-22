import os

import pymongo
from pymongo import MongoClient

from lib import Reminder


class Connector:

    client = None
    db = None
    class Scope():
        def __init__(self, is_private=False, guild_id=None, user_id=None):
            self.is_private = is_private
            self.guild_id = guild_id
            self.user_id = user_id


    @staticmethod
    def init():
        host = os.getenv('MONGO_CONN')
        port = int(os.getenv('MONGO_PORT'))

        uname = os.getenv('MONGO_ROOT_USER')
        pw = os.getenv('MONGO_ROOT_PASS')

        Connector.client = MongoClient(host=host, username=uname, password=pw, port=port)
        Connector.db = Connector.client.reminderBot


    @staticmethod
    def delete_guild(guild_id: int):
        Connector.db.settings.delete_one({'g_id': str(guild_id)})
        Connector.db.reminders.delete_many({'g_id': str(guild_id)})
        Connector.db.repeating.delete_many({'g_id': str(guild_id)})


    @staticmethod
    def get_timezone(guild_id: int):

        tz_json = Connector.db.settings.find_one({'g_id': str(guild_id)}, {'timezone': 1})

        if not tz_json:
            return 'UTC'
        else:
            return tz_json.get('timezone', 'UTC')


    @staticmethod
    def set_timezone(guild_id: int, timezone_str):

        Connector.db.settings.find_one_and_update({'g_id': str(guild_id)}, {'$set': {'timezone': timezone_str}}, new=False, upsert=True)


    @staticmethod
    def add_reminder(reminder: Reminder.Reminder):
        """save the reminder into the database

        Args:
            reminder (Reminder.Reminder): reminder object to be saved

        Returns:
            ObjectId: id of the database entry
        """
        insert_obj = Connector.db.reminders.insert_one(reminder._to_json())
        return insert_obj.inserted_id


    @staticmethod
    def get_elapsed_reminders(timestamp):

        rems =  list(Connector.db.reminders.find({'at': {'$lt': timestamp}}))
        rems = list(map(Reminder.Reminder, rems))

        # this method gets the entries
        print('WARN: requested reminder without deleting from db')
        return rems


    @staticmethod
    def pop_elapsed_reminders(timestamp):

        rems =  list(Connector.db.reminders.find({'at': {'$lt': timestamp}}))
        rems = list(map(Reminder.Reminder, rems))

        # this method pops the entries
        Connector.db.reminders.delete_many({'at': {'$lt': timestamp}})

        return rems

    @staticmethod
    def get_reminder_cnt():
        return Connector.db.reminders.count()


    @staticmethod
    def get_reminder_by_id(reminder_id):

        reminder = Connector.db.reminders.find_one({'_id': reminder_id})

        if reminder:
            return Reminder.Reminder(reminder)
        else:
            return None



    @staticmethod
    def delete_reminder(reminder_id):
        """delete the reminder with the given id

        Returns:
            bool: True if reminder deleted successfully
        """
        action = Connector.db.reminders.delete_one({'_id': reminder_id})
        return (action.deleted_count > 0)


    @staticmethod
    def get_scoped_reminders(scope: Scope, sort_return=True):
        """request all reminders from the db
           which match the required scope

        Args:
            scope (Scope): request scope (guild or private, always user bound)
            sort_return (bool): sort the reminders by elapsed time

        Returns:
            list: list of reminders
        """

        rems = []

        if scope.is_private and scope.user_id:
            rems =  Connector._get_user_private_reminders(scope.user_id)
        elif scope.user_id and scope.guild_id:
            rems =  Connector._get_user_reminders(scope.guild_id, scope.user_id)
        else:
            rems = []

        if sort_return:
            rems = sorted(rems, key=lambda r: r.at)
        
        return rems


    @staticmethod
    def _get_user_reminders(guild_id: int, user_id: int):

        rems = list(Connector.db.reminders.find({'g_id': str(guild_id), 'author': str(user_id)}))
        rems = list(map(Reminder.Reminder, rems))

        return rems

    @staticmethod
    def _get_user_private_reminders(user_id: int):

        rems = list(Connector.db.reminders.find({'g_id': None, 'author': str(user_id)}))
        rems = list(map(Reminder.Reminder, rems))

        return rems

    

    
   
