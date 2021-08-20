import os
from datetime import datetime

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
        rem_cursor = Connector.db.reminders.delete_many({'g_id': str(guild_id)})
        intvl_cursor = Connector.db.intervals.delete_many({'g_id': str(guild_id)})
        
        return (rem_cursor.deleted_count, intvl_cursor.deleted_count)


    @staticmethod
    def get_timezone(instance_id: int):
        
        # the settings key is 'g_id'
        # however guilds aswell as user ids are supported as key
        # for backwards compatibility with the database, the key name wasn't changed to instance_id
        tz_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'timezone': 1})

        if not tz_json:
            return 'UTC'
        else:
            return tz_json.get('timezone', 'UTC')


    @staticmethod
    def set_timezone(instance_id: int, timezone_str):
        
        # the settings key is 'g_id'
        # however guilds aswell as user ids are supported as key
        # for backwards compatibility with the database, the key name wasn't changed to instance_id
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'timezone': timezone_str}}, new=False, upsert=True)


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
    def add_interval(interval: Reminder.IntervalReminder):
        
        insert_obj = Connector.db.intervals.insert_one(interval._to_json())
        return insert_obj.inserted_id


    @staticmethod
    def update_interval_rules(interval: Reminder.IntervalReminder):

        intvl_js = interval._to_json()
        Connector.db.intervals.find_one_and_update({'_id': interval._id}, {'$set': {'rdates': intvl_js['rdates'],
                                                                                    'exdates': intvl_js['exdates'],
                                                                                    'rrules': intvl_js['rrules'],
                                                                                    'exrules': intvl_js['exrules']}}, new=False, upsert=False)

    @staticmethod
    def update_interval_at(interval: Reminder.IntervalReminder):
        
        if not interval.at:
            print(f'WARN: orphaned interval reminder {interval._id}.')
            at_ts = None
        else:
            at_ts = interval._to_json()['at']

        Connector.db.intervals.find_one_and_update({'_id': interval._id}, {'$set': {'at': at_ts}}, new=False, upsert=False)


    @staticmethod
    def delete_orphaned_intervals():

        op = Connector.db.intervals.delete_many({'at': {'$eq': None}})
        return op.deleted_count


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
    def get_pending_intervals(timestamp):

        intvl =  list(Connector.db.intervals.find({'at': {'$lt': timestamp}}))
        intvl = list(map(Reminder.IntervalReminder, intvl))

        return intvl


    @staticmethod
    def get_reminder_cnt():
        return Connector.db.reminders.count()


    @staticmethod
    def get_interval_cnt():
        return Connector.db.intervals.count()


    @staticmethod
    def get_reminder_by_id(reminder_id):

        reminder = Connector.db.reminders.find_one({'_id': reminder_id})

        if reminder:
            return Reminder.Reminder(reminder)
        else:
            return None
        
    @staticmethod
    def get_interval_by_id(interval_id):

        interval = Connector.db.intervals.find_one({'_id': interval_id})

        if interval:
            return Reminder.IntervalReminder(interval)
        else:
            return None


    @staticmethod
    def get_author_of_id(reminder_id):
        """return the author id of the given reminder id
           can be a plain reminder or an interval
           
           None if id not found
        """

        reminder = Connector.db.reminders.find_one({'_id': reminder_id}, {'author': 1})
        
        if not reminder:
            reminder = Connector.db.intervals.find_one({'_id': reminder_id}, {'author': 1})

        if reminder:
            return int(reminder['author'])
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
    def delete_interval(reminder_id):
        """delete the reminder with the given id

        Returns:
            bool: True if reminder deleted successfully
        """
        action = Connector.db.intervals.delete_one({'_id': reminder_id})
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
            #rems = sorted(rems, key=lambda r: r.at or datetime.utcnow())
            rems = sorted(rems)
        
        return rems


    @staticmethod
    def _get_user_reminders(guild_id: int, user_id: int):

        rems = list(Connector.db.reminders.find({'g_id': str(guild_id), 'author': str(user_id)}))
        rems = list(map(Reminder.Reminder, rems))

        intvl = list(Connector.db.intervals.find({'g_id': str(guild_id), 'author': str(user_id)}))
        intvl = list(map(Reminder.IntervalReminder, intvl))

        return rems + intvl

    @staticmethod
    def _get_user_private_reminders(user_id: int):

        rems = list(Connector.db.reminders.find({'g_id': None, 'author': str(user_id)}))
        rems = list(map(Reminder.Reminder, rems))

        intvl = list(Connector.db.intervals.find({'g_id': None, 'author': str(user_id)}))
        intvl = list(map(Reminder.IntervalReminder, intvl))

        return rems + intvl

    

    
   
