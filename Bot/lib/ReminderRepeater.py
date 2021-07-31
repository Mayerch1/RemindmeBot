from bson import ObjectId
import asyncio

from datetime import datetime, timedelta
from dateutil import tz
import dateutil.rrule as rr

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Analytics import Analytics
from lib.Reminder import Reminder, IntervalReminder
import lib.input_parser
import util.interaction


class _STM():
    def __init__(self):
        self.client = None
        self.timezone = None
        self.dm = None
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



def _add_rules(reminder, rrule=None, exrule=None, rdate=None, exdate=None):

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

async def _wait_rrule_input(stm):
    """loop until the user has entered a valid rrule
       or until a timeout was reached

    Args:
        stm (_STM): dm stm

    Returns:
        str: rrule string
    """

    dtstart = stm.reminder.first_at if isinstance(stm.reminder, IntervalReminder) else stm.reminder.at
    beta_limit = datetime(year=2022, month=1, day=1, hour=0, minute=0, second=0)

    def msg_check(msg):
        return msg.channel.id == stm.dm.id and\
                msg.author.id == stm.dm.recipient.id

    while True:
        try:
            message = await stm.client.wait_for('message', check=msg_check, timeout=10*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            return None

        rrule_input = message.content.lower()

        # test if the rule is valid by RFC
        # next check if the selected parameters
        # are within the allowed range,
        rule, error = _rule_normalize(rrule_input, dtstart)
        
        if not rule and error:
            embed = discord.Embed(title='Invalid rrule',
                                  color=0xff0000,
                                  description=error+'\nPlease try again.')
            stm.q_msg = await stm.dm.send(embed=embed)
            continue
        elif not rule:
            embed = discord.Embed(title='Invalid rrule',
                                  color=0xff0000,
                                  description='Unknown error occurred while parsing the rrule.\nPlease try again.')
            stm.q_msg = await stm.dm.send(embed=embed)
            continue


        if 'hourly' in rrule_input or\
             'minutely' in rrule_input or\
             'secondly' in rrule_input:

            embed = discord.Embed(title='Invalid rrule',
                                  color=0xff0000,
                                  description='Hourly repetitions are not supported in beta.')
            stm.q_msg = await stm.dm.send(embed=embed)
        else:
            return rule




async def _wait_input_date(stm):
    """loop until the user has entered a valid date
       or until a timeout was reached

    Args:
        stm (_STM): dm stm

    Returns:
        datetime: datetime object or None
    """

    utcnow = datetime.utcnow()
    
    def msg_check(msg):
        return msg.channel.id == stm.dm.id and\
                msg.author.id == stm.dm.recipient.id

    while True:
        try:
            message = await stm.client.wait_for('message', check=msg_check, timeout=5*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            return None

        date, info = lib.input_parser.parse(message.content, utcnow, stm.timezone)
        interval = date-utcnow

        if interval == timedelta(hours=0):
            embed = discord.Embed(title='Invalid input date',
                                  color=0xff0000,
                                  description=info + ' .\nTry again.')
            stm.q_msg = await stm.dm.send(embed=embed)

        elif interval < timedelta(hours=0):
            embed = discord.Embed(title='Input date was in the past', 
                                  color=0xff0000,
                                  description='Only dates in the future are allowed.\nTry again.')    
            stm.q_msg = await stm.dm.send(embed=embed)            
        else:
            return date


#======================
# Edit Rules and Dates
#======================


async def _add_date(stm):
    """ask the user to enter a new single occurrence date
       ask for validation of entered date

    Args:
        stm ([type]): [description]

    Returns:
        datetime: new date to be added
    """

    question_eb = discord.Embed(title='Add a single occurrence date',
                        description='Enter a date as allowed by the remindme parser (fuzzy or iso)\n')

    stm.q_msg = await stm.dm.send(embed=question_eb)
    rdate = await _wait_input_date(stm)

    accept = False
    msg = None
    if rdate:
        localized_date = rdate.replace(tzinfo=tz.UTC).astimezone(tz.gettz(stm.timezone))
        eb = discord.Embed(title='New single occurrence date',
                           description='Do you want to add the date `{:s}` as a new single occurrence?'\
                                        .format(localized_date.strftime('%Y-%m-%d %H:%M %Z')))
        msg = await stm.dm.send(embed=eb)
        accept = await util.interaction.wait_confirm_deny(stm.client, msg, 2*60, stm.dm.recipient)

    if not accept:
        eb = discord.Embed(title='No new date created', color=0xaa3333)
        if msg:
            await msg.edit(embed=eb)
        else:
            await stm.dm.send(embed=eb)


    stm.q_msg = await stm.dm.send('...')
    return rdate if accept else None


async def _add_exdate(stm):
    """ask the user to enter a new exclusion date
       ask for validation of entered date

    Args:
        stm ([type]): [description]

    Returns:
        datetime: new date to be added
    """

    question_eb = discord.Embed(title='Add a single exclusion date',
                        description='Enter a date as allowed by the remindme parser (fuzzy or iso)\n')

    stm.q_msg = await stm.dm.send(embed=question_eb)
    rdate = await _wait_input_date(stm)

    accept = False
    msg = None
    if rdate:
        localized_date = rdate.replace(tzinfo=tz.UTC).astimezone(tz.gettz(stm.timezone))
        eb = discord.Embed(title='New single exclusion',
                           description='Exclude `{:s}`?. The reminder will not be triggered on this specific date.'\
                                        .format(localized_date.strftime('%Y-%m-%d %H:%M %Z')))
        msg = await stm.dm.send(embed=eb)
        accept = await util.interaction.wait_confirm_deny(stm.client, msg, 2*60, stm.dm.recipient)

    if not accept:
        eb = discord.Embed(title='No new date excluded', color=0xaa3333)
        if msg:
            await msg.edit(embed=eb)
        else:
            await stm.dm.send(embed=eb)


    stm.q_msg = await stm.dm.send('...')
    return rdate if accept else None



async def _add_rrule(stm):
    question_eb = discord.Embed(title='Add a re-occurrence rule',
                        description='Enter an `RRULE`-string describing the repetition pattern. For the first beta implementation, please follow the link to an external `RRULE` generator\n')

    btn = manage_components.create_button(
        style=ButtonStyle.URL,
        label='RRULE Generator',
        url='https://www.textmagic.com/free-tools/rrule-generator'
    )
    link_btn = manage_components.create_actionrow(btn)

    stm.q_msg = await stm.dm.send(embed=question_eb, components=[link_btn])
    rrule = await _wait_rrule_input(stm)

    accept = False
    msg = None
    if rrule:
        eb = discord.Embed(title='New re-occurrence rule',
                           description='Add the rule `{:s}`?. The reminder is triggered according to this rule.'\
                                        .format(str(rrule)))
        msg = await stm.dm.send(embed=eb)
        accept = await util.interaction.wait_confirm_deny(stm.client, msg, 2*60, stm.dm.recipient)

    if not accept:
        eb = discord.Embed(title='No new rule added', color=0xaa3333)
        if msg:
            await msg.edit(embed=eb)
        else:
            await stm.dm.send(embed=eb)

    stm.q_msg = await stm.dm.send('...')
    return str(rrule) if accept else None



async def _add_exrule(stm):

    question_eb = discord.Embed(title='Add an exception rule',
                        description='Enter an `RRULE`-string describing the exception pattern. For the first beta implementation, please follow the link to an external `RRULE` generator\n')

    btn = manage_components.create_button(
        style=ButtonStyle.URL,
        label='RRULE Generator',
        url='https://www.textmagic.com/free-tools/rrule-generator'
    )
    link_btn = manage_components.create_actionrow(btn)

    stm.q_msg = await stm.dm.send(embed=question_eb, components=[link_btn])
    rrule = await _wait_rrule_input(stm)

    accept = False
    msg = None
    if rrule:
        eb = discord.Embed(title='New exception pattern',
                           description='Add the rule `{:s}`?. The reminder will not be triggered according to this rule.'\
                                        .format(str(rrule)))
        msg = await stm.dm.send(embed=eb)
        accept = await util.interaction.wait_confirm_deny(stm.client, msg, 2*60, stm.dm.recipient)

    if not accept:
        eb = discord.Embed(title='No new rule added', color=0xaa3333)
        if msg:
            await msg.edit(embed=eb)
        else:
            await stm.dm.send(embed=eb)

    stm.q_msg = await stm.dm.send('...')
    return str(rrule) if accept else None



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
        await intvl_ctx.defer(edit_origin=True)
        

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

            # TODO: show more info for selected role
            pass
        elif intvl_ctx.custom_id == 'repeater_del_return':
            return False
        else:
            return True

#==================
# STM core methods
#==================

async def _disable_components(stm):

    if stm.q_msg:
        for n_row in stm.navigation_rows:
            for c in n_row['components']:
                c['disabled'] = True
    
        try:
            await stm.q_msg.edit(components=[*stm.navigation_rows])
        except AttributeError:
            # if the stm exits outside the basic menu, nothing to be done 
            # here
            pass


async def _exit_stm(stm):
    """exit the stm, disable all components
        and send a goodbye message

    Args:
        stm (_STM): stm object
    """
    await stm.dm.send('If you wish to edit this reminder again, select it in the `/reminder_list` menu')
    await _disable_components(stm)
    


async def _interval_stm(client, dm, reminder, tz_str='UTC'):

    stm = _STM()
    stm.client = client
    stm.dm = dm
    stm.reminder = reminder
    stm.timezone = tz_str


    warn_eb = discord.Embed(title='INFO: Experimental Feature',
                            color=0xff833b,
                            description='This is released as a beta feature.')
    warn_eb.add_field(name='\u200b', value='If you want to give feedback for this feature, contact us '\
                                     'on the [support server](https://discord.gg/vH5syXfP) '\
                                      'or on [Github](https://github.com/Mayerch1/RemindmeBot)\n')

    await dm.send(embed=warn_eb)
                                        

    eb = stm.reminder.get_info_embed()
    await dm.send(content='Reminder under edit', embed=eb)

    stm.q_msg = await dm.send('...')

    while True:
        
        if isinstance(stm.reminder, IntervalReminder):
            # show existing rules and give option
            # this might be stuck in a selection loop for a while
            success = await _show_rule_deletion(stm)
            if not success:
                await _exit_stm(stm)
                return
            

        eb = discord.Embed(title='Add new rule',
                            description='Specify which type of rule you want to add to this event')

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Repeating Rule',
                custom_id='repeater_add_rrule'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Exception Rule',
                custom_id='repeater_add_exrule'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Single Date',
                custom_id='repeater_add_date'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Exception Date',
                custom_id='repeater_add_exdate'
            )
        ]
        stm.navigation_rows = [manage_components.create_actionrow(*buttons)]
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Return',
                custom_id='repeater_add_return'
            )
        ]
        stm.navigation_rows.extend([manage_components.create_actionrow(*buttons)])
        await stm.q_msg.edit(content='', embed=eb, components=[*stm.navigation_rows])

        try:
            action_ctx = await manage_components.wait_for_component(stm.client, components=[*stm.navigation_rows], timeout=10*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            await _exit_stm(stm)
            return

        await action_ctx.defer(edit_origin=True)
        await _disable_components(stm)

        if action_ctx.custom_id == 'repeater_add_rrule':
            rrule = await _add_rrule(stm)
            if rrule:
                stm.reminder = _add_rules(stm.reminder, rrule=rrule)
        elif action_ctx.custom_id == 'repeater_add_date':
            rdate = await _add_date(stm)
            if rdate:
                stm.reminder = _add_rules(stm.reminder, rdate=rdate)
        elif action_ctx.custom_id == 'repeater_add_exrule':
            exrule = await _add_exrule(stm)
            if exrule:
                stm.reminder = _add_rules(stm.reminder, exrule=exrule)
        elif action_ctx.custom_id == 'repeater_add_exdate':
            exdate = await _add_exdate(stm)
            if exdate:
                stm.reminder = _add_rules(stm.reminder, exdate=exdate)
        elif action_ctx.custom_id == 'repeater_add_return':
            if isinstance(stm.reminder, IntervalReminder):
                continue
            else:
                await _exit_stm(stm)
                return

        
        if not stm.reminder.at:
            eb = discord.Embed(title='Orphan warning',
                            color=0xaa3333,
                            description='The reminder has no further events pending. It will be deleted soon, if no new rule is added')
            await stm.dm.send(embed=eb)


#=====================
# Setup/Entry methdos
#=====================

async def transfer_interval_setup(client, dm_stm, reminder):
    """take the existing dm session and append the interval setup
       the changes made by the user are directly saved into the DB
       the reminder is modified in place to reflect usage

       WARNING: the reminder might be converted
                Reminder <-> IntervalReminder

    Args:
        client (discord): discord Client
        dm_stm (STM): dm STM, used to get dm session
        reminder (Reminder): or IntervalReminder
    """

    dm = dm_stm.dm
    reminder = reminder

    if dm_stm.scope.is_private:
        tz_instance = dm_stm.scope.user_id
    else:
        tz_instance = dm_stm.scope.guild_id
    
    tz_str = Connector.get_timezone(tz_instance)


    await _interval_stm(client, dm, reminder, tz_str)

    
async def spawn_interval_setup(client, ctx: ComponentContext, reminder_id: ObjectId):
    """take the given reminder id and spawn a dm with the author of the ctx
       if dm cannot be created, an error is shown
       if the reminder doesn't exist, an error is shown

       take the existing dm session and append the interval setup
       the changes made by the user are directly saved into the DB
       the reminder is modified in place to reflect usage

    Args:
        client (discord): discord Client
        ctx (ComponentContext): the component click context  
        reminder_id (ObjectId): id of the requested reminder
    """

    dm = await ctx.author.create_dm()
    reminder = Connector.get_reminder_by_id(reminder_id)


    if not ctx.guild_id:
        tz_str = Connector.get_timezone(ctx.author_id)
    else:
        tz_str = Connector.get_timezone(ctx.guild_id)

    if not reminder:
        await ctx.send('The reminder seems to be either deleted, or has already expired', hidden=True)
        return
    
    # test if the bot can send a message to the newly created DM channel
    # or if the creation has failed, notify the user accordingly
    try:
        test_msg = await dm.send('...')
    except discord.errors.Forbidden as e:
        embed = discord.Embed(title='Missing DM Permission', 
                                description='You can only edit intervals in your DMs. Please '\
                                            '[change your preferences]({:s}) and invoke this '\
                                            'command again.\n You can revert the changes later on.'.format(r'https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-'),
                                color=0xff0000)

        await ctx.send(embed=embed, hidden=True)
        return
    
    await ctx.send('Have a look at your DMs to edit this reminder', hidden=True)
    await test_msg.delete()
    await _interval_stm(client, dm, reminder, tz_str)
