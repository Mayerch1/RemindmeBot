import os
from datetime import datetime
from enum import Enum
from typing import Union

import pymongo
from pymongo import MongoClient

from lib.Reminder import Reminder, IntervalReminder
from lib.CommunitySettings import CommunitySettings


import logging



log = logging.getLogger('Remindme.Connector')



class Connector:

    client = None
    db = None
    class Scope():
        def __init__(self, is_private=False, guild_id=None, user_id=None):
            self.is_private = is_private
            self.guild_id = guild_id
            self.user_id = user_id
            self.instance_id = self.guild_id or self.user_id

    class ReminderType(Enum):
        TEXT_ONLY = 1
        HYBRID = 2
        EMBED_ONLY = 3
        BAREBONE = 4

    class AutoDelete(Enum):
        TIMEOUT = 1
        NEVER = 2
        HIDE = 3
        
    class CommunityMode(Enum):
        DISABLED = 1
        ENABLED = 2
        
    

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
    def  get_reminder_type(instance_id: int) -> ReminderType:
        
        # keep g_id as key for backwards compatibility
        rem_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'reminder_type': 1})
        
        if not rem_json:
            return Connector.ReminderType.HYBRID
        else:
            return Connector.ReminderType[rem_json.get('reminder_type', Connector.ReminderType.HYBRID.name)]
    
        
    @staticmethod
    def set_auto_delete(instance_id: int, delete_type: AutoDelete):
        
        # keep g_id as key for backwards compatibility
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'auto_delete': delete_type.name}}, new=False, upsert=True)
        
    @staticmethod
    def  get_auto_delete(instance_id: int):
        
        # keep g_id as key for backwards compatibility
        rem_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'auto_delete': 1})
        
        if not rem_json:
            return Connector.AutoDelete.TIMEOUT
        else:
            return Connector.AutoDelete[rem_json.get('auto_delete', Connector.AutoDelete.TIMEOUT.name)]
        
    @staticmethod
    def set_community_mode(instance_id: int, comm_type: CommunityMode):
        
        # keep g_id as key for backwards compatibility
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'community': comm_type.name}}, new=False, upsert=True)
        
    @staticmethod
    def get_community_mode(instance_id: int):
        
        # keep g_id as key for backwards compatibility
        rem_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'community': 1})
        
        if not rem_json:
            return Connector.CommunityMode.DISABLED
        else:
            return Connector.CommunityMode[rem_json.get('community', Connector.CommunityMode.DISABLED.name)]


    @staticmethod
    def get_legacy_interval_count():
        return Connector.db.settings.count_documents({'legacy_interval': True})


    @staticmethod
    def set_legacy_interval(instance_id: int, mode: bool):
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'legacy_interval': mode}}, new=False, upsert=True)


    @staticmethod
    def is_legacy_interval(instance_id: int) -> bool:
        """check if the instance uses legacy intervals
           if no entry exists, legacy is assumed for backwards compatibility
        """
        exp_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'legacy_interval': 1})
        
        if not exp_json:
            return True
        else:
            return exp_json.get('legacy_interval', True)


    @staticmethod
    def get_experimental_count():
        return Connector.db.settings.count_documents({'experimental': True})


    @staticmethod
    def set_experimental(instance_id: int, mode: bool):
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'experimental': mode}}, new=False, upsert=True)
    
    @staticmethod
    def is_experimental(instance_id: int):
        
        exp_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'experimental': 1})
        
        if not exp_json:
            return False
        else:
            return exp_json.get('experimental', False)


    @staticmethod
    def get_community_count():
        return Connector.db.settings.count_documents({'community': 'ENABLED'})


    @staticmethod
    def set_community_settings(instance_id: int, settings: CommunitySettings) -> CommunitySettings:
        
        settings_json = settings._to_json()
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'community_settings': settings_json}}, new=False, upsert=True)
    
    
    @staticmethod
    def set_community_setting(instance_id: int, setting_name: str, value: bool):
        
        dummy_settings = CommunitySettings()
        if not hasattr(dummy_settings, setting_name):
            raise ValueError(f'{setting_name} is not an attribute of CommunitySettings')
        
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {f'community_settings.{setting_name}': value}}, new=False, upsert=True)
    
    @staticmethod
    def get_community_settings(instance_id: int) -> CommunitySettings:
        
        # keep g_id as key for backwards compatibility
        comm_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'community_settings': 1})
        
        if not comm_json:
            return CommunitySettings()
        else:
            return CommunitySettings(comm_json.get('community_settings', {}))


    @staticmethod
    def set_moderators(guild_id: int, moderators: list[Union[int, str]]):
        """set a list as new moderators, this list overwrites all existing mods

        Args:
            guild_id (int): guild id, DMs are not supported
            moderators (list): list of moderators (can be ints or strings)
        """
        
        # keep g_id as key for backwards compatibility
        Connector.db.settings.find_one_and_update({'g_id': str(guild_id)}, {'$set': {'moderators': list(map(str, moderators))}}, new=False, upsert=True)


    @staticmethod
    def get_moderators(instance_id: int):
        
        # keep g_id as key for backwards compatibility
        mod_json = Connector.db.settings.find_one({'g_id': str(instance_id)}, {'moderators': 1})
        
        if not mod_json:
            return []
        else:
            return list(map(int, mod_json.get('moderators', [])))
    
    @staticmethod
    def is_moderator(user_roles: list):
        """check if any of the user roles are within the noted moderator lists
           query is implicitely protected from cross-guild access

        Args:
            user_roles (list): list of role ids
            guild_id (int): id of the guild, DMs not supported (will always return False)
            
        Return:
            bool: True if any of the user roles is a moderator role
        """
        
        # this query is not secured by a guild_id filter
        # this will not cause any issues, as role_ids are guaranteed to be unique
        #
        # as the roles are already filtered by guild, 
        # this will only generate hits for this specific guild
        
        if not user_roles:
            return False
        
        if not isinstance(user_roles, list):
            raise TypeError('user_roles must be of type list')
        
        if isinstance(user_roles[0], str):
            user_roles = user_roles
        elif isinstance(user_roles[0], int):
            user_roles = list(map(str, user_roles))
        elif hasattr(user_roles[0], 'id'):
            # convert to id
            user_roles = list(map(lambda r: str(r.id), user_roles))
        else:
            raise TypeError('user_roles must hold entities of type str, int or entities must have .id attribute')
        
        result = Connector.db.settings.find_one({'moderators': {'$in': user_roles}})
        return result != None

        
    @staticmethod
    def set_reminder_type(instance_id: int, reminder_type: ReminderType):
        
        # keep g_id as key for backwards compatibility
        Connector.db.settings.find_one_and_update({'g_id': str(instance_id)}, {'$set': {'reminder_type': reminder_type.name}}, new=False, upsert=True)


    @staticmethod
    def add_reminder(reminder: Reminder):
        """save the reminder into the database

        Args:
            reminder (Reminder): reminder object to be saved

        Returns:
            ObjectId: id of the database entry
        """
        insert_obj = Connector.db.reminders.insert_one(reminder._to_json())
        return insert_obj.inserted_id

    @staticmethod
    def add_interval(interval: IntervalReminder):
        
        insert_obj = Connector.db.intervals.insert_one(interval._to_json())
        return insert_obj.inserted_id


    @staticmethod
    def update_interval_rules(interval: IntervalReminder):

        intvl_js = interval._to_json()
        Connector.db.intervals.find_one_and_update({'_id': interval._id}, {'$set': {'rdates': intvl_js['rdates'],
                                                                                    'exdates': intvl_js['exdates'],
                                                                                    'rrules': intvl_js['rrules'],
                                                                                    'exrules': intvl_js['exrules']}}, new=False, upsert=False)

    @staticmethod
    def update_reminder_at(reminder: Reminder):

        at_ts = reminder._to_json()['at']
        Connector.db.reminders.find_one_and_update({'_id': reminder._id}, {'$set': {'at': at_ts}}, new=False, upsert=False)


    @staticmethod
    def update_interval_at(interval: IntervalReminder):
        
        if not interval.at:
            log.warning(f'Orphaned interval reminder {interval._id}.')
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
        rems = list(map(Reminder, rems))

        # this method gets the entries
        log.warning('Requested reminder without deleting from db')
        return rems


    @staticmethod
    def pop_elapsed_reminders(timestamp):

        rems =  list(Connector.db.reminders.find({'at': {'$lt': timestamp}}))
        rems = list(map(Reminder, rems))

        # this method pops the entries
        Connector.db.reminders.delete_many({'at': {'$lt': timestamp}})

        return rems

    @staticmethod
    def get_pending_intervals(timestamp):

        intvl =  list(Connector.db.intervals.find({'at': {'$lt': timestamp}}))
        intvl = list(map(IntervalReminder, intvl))

        return intvl


    @staticmethod
    def get_reminder_cnt():
        return Connector.db.reminders.count_documents({})


    @staticmethod
    def get_interval_cnt():
        return Connector.db.intervals.count_documents({})


    @staticmethod
    def get_reminder_by_id(reminder_id):

        reminder = Connector.db.reminders.find_one({'_id': reminder_id})

        if reminder:
            return Reminder(reminder)
        else:
            return None
        
    @staticmethod
    def get_interval_by_id(interval_id):

        interval = Connector.db.intervals.find_one({'_id': interval_id})

        if interval:
            return IntervalReminder(interval)
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
    def set_reminder_message(reminder_id, message: str):
        """set the message of the given reminder
           can be Reminder or Interval
           must already be existing in db

        Args:
            reminder_id (_type_): _description_
            message (str): _description_

        Returns:
            _type_: _description_
        """

        result = Connector.db.reminders.find_one_and_update({
            '_id': reminder_id,}, {'$set': {'msg': message}}, new=False, upsert=False
        )

        if not result:
            result = Connector.db.intervals.find_one_and_update({
            '_id': reminder_id,}, {'$set': {'msg': message}}, new=False, upsert=False
        )

        return (result is not None)


    @staticmethod
    def set_reminder_title(reminder_id, title: str):
        """set the optional title for the given reminder Id
           can be Reminder or Interval
           reminder must already be stored into db

        Args:
            reminder_id (ObjectId): id of reminder
            title (str): new title

        Returns:
            bool: True if set was successfull
        """

        result = Connector.db.reminders.find_one_and_update({
            '_id': reminder_id,}, {'$set': {'title': title}}, new=False, upsert=False
        )

        if not result:
            result = Connector.db.intervals.find_one_and_update({
            '_id': reminder_id,}, {'$set': {'title': title}}, new=False, upsert=False
        )

        return (result is not None)

    @staticmethod
    def set_reminder_channel(reminder_id, channel_id: int, channel_name:str=None):
        """change the channel id of a given reminder
           method tries to find reminder, if not exists
           method will assume an interval

        Args:
            reminder_id (ObjectId): reminder/interval ID

        Returns:
            bool: True if set was successfull
        """
        
        # upsert with channel_name
        if channel_name:
            result = Connector.db.reminders.find_one_and_update({'_id': reminder_id}, 
                                                            {'$set': {'ch_id': str(channel_id), 'ch_name': str(channel_name)}}, 
                                                            new=False, 
                                                            upsert=False)
            if not result:
                result = Connector.db.intervals.find_one_and_update({'_id': reminder_id}, 
                                                                {'$set': {'ch_id': str(channel_id), 'ch_name': str(channel_name)}}, 
                                                                new=False, 
                                                                upsert=False)

        # upsert without channel name
        else:
            result = Connector.db.reminders.find_one_and_update({'_id': reminder_id}, 
                                                            {'$set': {'ch_id': str(channel_id)}}, 
                                                            new=False, 
                                                            upsert=False)
        
            if not result:
                result = Connector.db.intervals.find_one_and_update({'_id': reminder_id}, 
                                                                    {'$set': {'ch_id': str(channel_id)}}, 
                                                                    new=False, 
                                                                    upsert=False)
            
        return (result is not None)
        
        


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
        rems = list(map(Reminder, rems))

        intvl = list(Connector.db.intervals.find({'g_id': str(guild_id), 'author': str(user_id)}))
        intvl = list(map(IntervalReminder, intvl))

        return rems + intvl

    @staticmethod
    def _get_user_private_reminders(user_id: int):

        rems = list(Connector.db.reminders.find({'g_id': None, 'author': str(user_id)}))
        rems = list(map(Reminder, rems))

        intvl = list(Connector.db.intervals.find({'g_id': None, 'author': str(user_id)}))
        intvl = list(map(IntervalReminder, intvl))

        return rems + intvl

    

    
   
