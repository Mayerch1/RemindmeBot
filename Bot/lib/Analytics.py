from datetime import datetime, timedelta
from enum import Enum

import prometheus_client
from prometheus_client import Counter, Histogram, Gauge

import _thread

from flask import Flask, request, Response
from waitress import serve

from lib.Reminder import Reminder, IntervalReminder


class Types:
    class ReminderType(Enum):
        ONE_SHOT = 0
        REPEATING = 1

    class ReminderCreation(Enum):
        NEW = 0
        FROM_ONE_SHOT = 1
        FROM_REPEATING = 2

    class ReminderScope(Enum):
        GUILD = 0
        PRIVATE = 1

    class ReminderTarget(Enum):
        SELF = 0
        FOREIGN = 1

    class DeleteAction(Enum):
        LISTING = 0
        DIRECT_BTN = 1
        ORPHAN = 2

    class CreationFailed(Enum):
        INVALID_F_STR = 0
        PAST_DATE = 1

class Analytics:

    CONTENT_TYPE_LATEST = str('text/plain; version=0.0.4; charset=utf-8')

    REMINDER_CREATED_CNT = Counter(
        'reminder_created_cnt', 'Created Reminders Count', 
        ['shard', 'type', 'scope', 'target', 'creation_type']
    )

    REMINDER_DURATION = Histogram(
        'reminder_duration', 'Show Duration information of created reminders',
        buckets=(
            5*60,
            30*60,
            60*60,
            12*(60*60),
            24*(60*60),
            48*(60*60),
            7*(24*60*60),
            14*(24*60*60),
            30*(24*60*60),
            3*(30*24*60*60),
            6*(30*24*60*60),
            12*(30*24*60*60),
            24*(30*24*60*60),
            48*(30*24*60*60),
            float('inf')
        )
    )

    REMINDER_DELETED_CNT = Counter(
        'reminder_deleted_cnt', 'Deleted Reminders Count',
        ['shard', 'type', 'action']
    )

    GUILD_ADDED_CNT = Counter(
        'guild_added_cnt', 'Guilds the bot was added to'
    )

    GUILD_LEAVE_CNT = Counter(
        'guild_removed_cnt', 'Guilds the bot left/was removed from'
    )

    GUILD_CNT = Gauge(
        'guild_cnt', 'Total guild count of the bot'
    )

    REMINDER_CNT = Gauge(
        'reminder_cnt', 'Total count of reminders',
        ['shard', 'type']
    )

    REMINDER_CREATION_FAILED = Counter(
        'reminder_creation_failed', 'Failed reminder creation',
        ['shard', 'reason']
    )

    HELP_PAGE_CNT = Counter(
        'help_page_cnt', 'Number of calls to helppage',
        ['shard', 'page']
    )

    RULESET_ADDED_CNT = Counter(
        'ruleset_added_cnt', 'Rulesets added to repeating reminders',
        ['shard']
    )

    RULESET_REMOVED_CNT = Counter(
        'ruleset_removed_cnt', 'Rulesets removed from repeating reminders',
        ['shard']
    )

    UNEXPECTED_EXCEPTION = Counter(
        'unexpected_exception_cnt', 'Hold all caught unhandled exceptions',
        ['shard', 'ex_type']
    )
    
    UNDELIVERED_REMINDER = Counter(
        'undelivered_reminders', 'Reminders which couldn\'t be shown to the user',
        ['shard', 'type', 'scope', 'target']
    )

    app = Flask(__name__)

    @staticmethod
    def _waitress_thread(name, app, host, port):
        serve(app, host=host, port=port)


    @staticmethod
    def init():
        host = '0.0.0.0'
        port = 9091

        _thread.start_new_thread(Analytics._waitress_thread, ('flask server', Analytics.app, host, port))
        print(f'Analytics Webserver started on {host}:{port}')


    @app.route('/metrics')
    def metrics():
        return Response(prometheus_client.generate_latest(), mimetype=Analytics.CONTENT_TYPE_LATEST)

    #=========================
    # Analytics interface
    # used to collect data
    #=========================

    @staticmethod
    def reminder_created(reminder: Reminder, shard:int =0, from_interval=False, direct_interval=False):
        
        if isinstance(reminder, IntervalReminder):
            r_type = Types.ReminderType.REPEATING
        else:
            r_type = Types.ReminderType.ONE_SHOT

        if reminder.author == reminder.target:
            r_tgt = Types.ReminderTarget.SELF
        else:
            r_tgt = Types.ReminderTarget.FOREIGN

        if reminder.g_id:
            r_scope = Types.ReminderScope.GUILD
        else:
            r_scope = Types.ReminderScope.PRIVATE

        if from_interval:
            r_creation = Types.ReminderCreation.FROM_REPEATING
        elif isinstance(reminder, IntervalReminder) and not direct_interval:
            r_creation = Types.ReminderCreation.FROM_ONE_SHOT
        else:
            r_creation = Types.ReminderCreation.NEW

        interval = (reminder.at - datetime.utcnow()).total_seconds()


        Analytics.REMINDER_CREATED_CNT.labels(str(shard), 
                                                r_type.name, 
                                                r_scope.name, 
                                                r_tgt.name, 
                                                r_creation.name
                                            ).inc()

        Analytics.REMINDER_DURATION.observe(interval)


    @staticmethod
    def reminder_deleted(action: Types.DeleteAction, shard:int =0):
        Analytics.REMINDER_DELETED_CNT.labels(str(shard), Types.ReminderType.ONE_SHOT.name, action.name).inc()
        
    @staticmethod
    def interval_deleted(action: Types.DeleteAction, shard:int =0):
        Analytics.REMINDER_DELETED_CNT.labels(str(shard), Types.ReminderType.REPEATING.name, action.name).inc()

    @staticmethod
    def guild_added():
        Analytics.GUILD_ADDED_CNT.inc()

    @staticmethod
    def guild_removed():
        Analytics.GUILD_LEAVE_CNT.inc()

    @staticmethod
    def guild_cnt(guild_cnt:int):
        Analytics.GUILD_CNT.set(guild_cnt)

    @staticmethod
    def reminder_cnt(rem_cnt:int, shard:int =0):
        Analytics.REMINDER_CNT.labels(str(shard), Types.ReminderType.ONE_SHOT.name).set(rem_cnt)

    @staticmethod
    def interval_cnt(intvl_cnt:int, shard:int =0):
        Analytics.REMINDER_CNT.labels(str(shard), Types.ReminderType.REPEATING.name).set(intvl_cnt)

    @staticmethod
    def reminder_creation_failed(fail_type: Types.CreationFailed, shard:int =0):
        Analytics.REMINDER_CREATION_FAILED.labels(str(shard), fail_type.name).inc()

    @staticmethod
    def help_page_called(page_name:str, shard:int =0):
        Analytics.HELP_PAGE_CNT.labels(str(shard), page_name).inc()

    @staticmethod
    def ruleset_added(shard:int =0):
        Analytics.RULESET_ADDED_CNT.labels(str(shard)).inc()

    @staticmethod
    def ruleset_removed(shard:int =0):
        Analytics.RULESET_REMOVED_CNT.labels(str(shard)).inc()

    @staticmethod
    def register_exception(exception, shard:int = 0):
        ex_type = type(exception).__name__
        print(f'exposing exception counter \'{ex_type}\'')
        Analytics.UNEXPECTED_EXCEPTION.labels(str(shard), ex_type).inc()
        
    @staticmethod
    def reminder_not_delivered(reminder, shard:int = 0):
        
        if isinstance(reminder, IntervalReminder):
            r_type = Types.ReminderType.REPEATING
        else:
            r_type = Types.ReminderType.ONE_SHOT

        if reminder.author == reminder.target:
            r_tgt = Types.ReminderTarget.SELF
        else:
            r_tgt = Types.ReminderTarget.FOREIGN

        if reminder.g_id:
            r_scope = Types.ReminderScope.GUILD
        else:
            r_scope = Types.ReminderScope.PRIVATE

        Analytics.UNDELIVERED_REMINDER.labels(str(shard), r_type.name, r_scope.name, r_tgt.name).inc()