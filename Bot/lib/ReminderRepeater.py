from bson import ObjectId
import asyncio

from datetime import datetime, timedelta
from dateutil import tz
import dateutil.rrule as rr

import discord
from discord.ext import commands, tasks

from lib.Connector import Connector
from lib.Analytics import Analytics
from lib.Reminder import Reminder, IntervalReminder
import lib.input_parser
import util.interaction

from lib.CommunitySettings import CommunitySettings, CommunityAction


class _STM():
    def __init__(self):
        self.client = None
        self.timezone = None
        self.dm = None
        self.instance_id = None
        self.reminder = None
        self.q_msg = None
        self.navigation_rows = []

#====================
# Transformation Ops
#====================

def _reminder_to_interval(reminder: Reminder):
    """convert the Reminder into an IntervalReminder
       push transaction onto db
       return new IntervalReminder Object
       WARN: reminder might be orphaned and requires rules to be added

    Args:
        reminder (Reminder): old reminder       

    Returns:
        IntervalReminder: new reminder object
    """

    # create new IntervalReminder
    old_reminder = reminder
    reminder = IntervalReminder(old_reminder._to_json())

    # update the occurrence to optimise database fetches
    reminder.first_at = old_reminder.at
    # keep reminder 'at' at old val for now

    new_id = Connector.add_interval(reminder)
    Connector.delete_reminder(old_reminder._id)

    Analytics.reminder_created(reminder)

    reminder._id = new_id
    return reminder



def _interval_to_reminder(reminder: IntervalReminder):

    old_reminder = reminder
    reminder = Reminder(reminder._to_json())
    reminder.at = old_reminder.first_at

    new_id = Connector.add_reminder(reminder)
    Connector.delete_interval(old_reminder._id)
    
    Analytics.reminder_created(reminder, from_interval=True)

    reminder._id = new_id
    return reminder



def add_rules(reminder, rrule=None, exrule=None, rdate=None, exdate=None) -> IntervalReminder:
    """add the given rules to the given reminder
       converts the reminder to Intevral if not done yet

    Args:
        reminder (_type_): _description_
        rrule (_type_, optional): _description_. Defaults to None.
        exrule (_type_, optional): _description_. Defaults to None.
        rdate (_type_, optional): _description_. Defaults to None.
        exdate (_type_, optional): _description_. Defaults to None.

    Returns:
        IntervalReminder: the converted  reminder
    """

    if type(reminder) == Reminder:
        reminder = _reminder_to_interval(reminder)

    if rrule:
        reminder.rrules.append(rrule)
    
    if exrule:
        reminder.exrules.append(exrule)

    if rdate:
        reminder.rdates.append(rdate)

    if exdate:
        reminder.exdates.append(exdate)


    reminder.at = reminder.next_trigger(datetime.utcnow())
    Connector.update_interval_rules(reminder)
    Connector.update_interval_at(reminder)

    Analytics.ruleset_added()

    return reminder


def _rm_rules(reminder, rule_idx=None):

    utcnow = datetime.utcnow()

    if rule_idx is None:
        return reminder

    reminder.delete_rule_idx(rule_idx)
    reminder.at = reminder.next_trigger(datetime.utcnow())

    rules_cnt = reminder.get_rule_cnt()

    # if reminder has no further rules left over
    # and .at is in the future, set it as default Reminder
    if rules_cnt == 0 and reminder.at and reminder.at > utcnow:
        reminder = _interval_to_reminder(reminder)
        Analytics.ruleset_removed()
        return reminder

    # if reminder has no further occurrence
    # it is kept as orphaned reminder
    # it may or may not have some rules set
    # it's deleted in both cases within the next 24h

    # if at is None
    # the reminder is orphaned, a warning can be displayed by a higher layer
    Connector.update_interval_rules(reminder)
    Connector.update_interval_at(reminder)
    Analytics.ruleset_removed()

    return reminder


def _rule_normalize(rule_str, dtstart):
    """generate the rrule of the given rrule string
       if the string contains timezone based offsets (iso dates)
       they are converted into the non-timezone aware utc equivalent

    Args:
        rule_str ([type]): [description]
        dtstart ([type]): [description]

    Returns:
        [type]: [description]
    """

    try:
        rule = rr.rrulestr(rule_str)
    except Exception as e:
        return None, str(e)

    until = rule._until
    until_utc = None

    if until:
        # convert the until date to non-tz aware
        until_utc = until.astimezone(tz.UTC)
        until_utc = until_utc.replace(tzinfo=None)

    try:
        rule = rr.rrulestr(rule_str, dtstart=dtstart, ignoretz=True)
    except Exception as e:
        return None, str(e)

    if until_utc:
        rule = rule.replace(until=until_utc)

    return rule, None


#====================
# I/O Helper Methods
#====================


#======================
# Edit Rules and Dates
#======================


async def _show_rule_deletion(stm):

    eb = discord.Embed(title='Show/Delete existing rules',
                            description='You can show more detailed information for existing rules.\n'\
                                        'You can aswell delete selected rules/dates\n')


    def set_stm_reminder_comps(stm, select_idx=None):
        
        if isinstance(stm.reminder, IntervalReminder):
            rules = stm.reminder.get_rule_dicts()
        else:
            rules = []

        if len(rules) > 0:
            if select_idx != None:
                rules[select_idx]['default'] = True

            rule_options = [manage_components.create_select_option(label=r['label'], 
                                                                    description=r['descr'], 
                                                                    value=str(i),
                                                                    default=r['default']) for i, r in enumerate(rules)]

            rule_selection = (
                manage_components.create_select(
                    custom_id='repeater_delete_existsing_selection',
                    placeholder='Select a rule/date for more info',
                    min_values=1,
                    max_values=1,
                    options=rule_options
                )
            )
            stm.navigation_rows = [manage_components.create_actionrow(rule_selection)]

        else:
            stm.navigation_rows = []


        buttons = [
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Add New Rule',
                custom_id='repeater_skip_delete',
                disabled=len(rules) >= 25
            ),
            manage_components.create_button(
                style=ButtonStyle.danger,
                label='Delete Selected',
                custom_id='repeater_del_selected',
                disabled=(select_idx==None)
            )
        ]
        stm.navigation_rows.extend([manage_components.create_actionrow(*buttons)])

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Return',
                custom_id='repeater_del_return'
            )
        ]
        stm.navigation_rows.extend([manage_components.create_actionrow(*buttons)])


    set_stm_reminder_comps(stm, None)
    await stm.q_msg.edit(embed=eb, components=[*stm.navigation_rows])


    selected_idx = None
    while True:
        try:
            intvl_ctx = await manage_components.wait_for_component(stm.client, components=stm.navigation_rows, timeout=10*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            await _exit_stm(stm)
            return False
        
        try:
            await intvl_ctx.defer(edit_origin=True)
        except discord.NotFound:
            # just try again
            continue
        

        if intvl_ctx.custom_id == 'repeater_del_selected':

            stm.reminder = _rm_rules(stm.reminder, rule_idx=selected_idx)
            selected_idx = None
            set_stm_reminder_comps(stm, selected_idx)
            await stm.q_msg.edit(components=[*stm.navigation_rows])

            if not stm.reminder.at:
                eb = discord.Embed(title='Orphan warning',
                                color=0xaa3333,
                                description='The reminder has no further events pending. It will be deleted soon, if no new rule is added')
                await stm.dm.send(embed=eb)

        elif intvl_ctx.custom_id == 'repeater_delete_existsing_selection':

            selected_idx = int(intvl_ctx.selected_options[0])
            set_stm_reminder_comps(stm, selected_idx)
            await stm.q_msg.edit(components=[*stm.navigation_rows])

        elif intvl_ctx.custom_id == 'repeater_del_return':
            return False
        else:
            return True

#==================
# STM core methods
#==================
async def dummy():
    # TODO: show this on rule deletion    
    if not stm.reminder.at:
        eb = discord.Embed(title='Orphan warning',
                        color=0xaa3333,
                        description='The reminder has no further events pending. It will be deleted soon, if no new rule is added')
        await stm.dm.send(embed=eb)
