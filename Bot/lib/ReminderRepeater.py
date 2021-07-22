from bson import ObjectId
import asyncio

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Reminder import Reminder, IntervalReminder


class _STM():
    def __init__(self):
        self.client = None
        self.dm = None
        self.reminder = None
        self.q_msg = None
        self.navigation_rows = []


#====================
# I/O Helper Methods
#====================



#======================
# Edit Rules and Dates
#======================

async def _add_rrule(stm):
    pass

async def _add_date(stm):
    pass

async def _add_exrule(stm):
    pass

async def _add_exdate(stm):
    pass


async def _show_rule_deletion(stm):

    eb = discord.Embed(title='Show/Delete existing rules',
                            description='You can show more detailed information for existing rules.\n'\
                                        'You can aswell delete selected rules/dates\n')

    rule_options = [manage_components.create_select_option(label='Test', value='1')]
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
    buttons = [
        manage_components.create_button(
            style=ButtonStyle.success,
            label='Add New Rule',
            custom_id='repeater_skip_delete'
        ),
        manage_components.create_button(
            style=ButtonStyle.danger,
            label='Delete Selected',
            custom_id='repeater_del_selected'
        )
    ]

    stm.navigation_rows.extend([manage_components.create_actionrow(*buttons)])
    await stm.q_msg.edit(embed=eb, components=[*stm.navigation_rows])


    try:
        intvl_ctx = await manage_components.wait_for_component(stm.client, components=stm.navigation_rows, timeout=10*60)
    except asyncio.exceptions.TimeoutError:
        # abort the deletion
        await _exit_stm(stm)
        return False
    await intvl_ctx.defer(edit_origin=True)
    

    if intvl_ctx.custom_id == 'repeater_del_selected':
        # TODO: delete the selected role
        pass
    elif intvl_ctx.custom_id == 'repeater_delete_existsing_selection':
        # TODO: show more info for selected role
        pass
    # 'repeater_skip_delete' will advance to 'add_x' step

    return True


#==================
# STM core methods
#==================

async def _exit_stm(stm):
    """exit the stm, disable all components
        and send a goodbye message

    Args:
        stm (_STM): stm object
    """
    await stm.dm.send('If you wish to edit this reminder again, select it in the `/reminder_list` menu')

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


async def _interval_stm(client, dm, reminder):

    stm = _STM()
    stm.client = client
    stm.dm = dm
    stm.reminder = reminder

    eb = stm.reminder.get_info_embed()
    await dm.send(content='Reminder under edit', embed=eb)

    stm.q_msg = await dm.send('.')

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
                label='Add Single Date',
                custom_id='repeater_add_date'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Exception Rule',
                custom_id='repeater_add_exrule'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Add Exception Date',
                custom_id='repeater_add_exdate'
            )
        ]
        stm.navigation_rows = [manage_components.create_actionrow(*buttons)]
        await stm.q_msg.edit(embed=eb, components=[*stm.navigation_rows])

        try:
            action_ctx = await manage_components.wait_for_component(stm.client, components=stm.navigation_rows, timeout=10*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            await _exit_stm(stm)
            return

        if action_ctx == 'repeater_add_rrule':
            await _add_rrule(stm)
        elif action_ctx == 'repeater_add_date':
            await _add_date(stm)
        elif action_ctx == 'repeater_add_exrule':
            await _add_exrule(stm)
        elif action_ctx == 'repeater_add_exdate':
            await _add_exdate(stm)


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

    await _interval_stm(client, dm, reminder)

    
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

    if not reminder:
        await ctx.send('The reminder seems to be either deleted, or has already expired', hidden=True)
        return
    
    # test if the bot can send a message to the newly created DM channel
    # or if the creation has failed, notify the user accordingly
    try:
        test_msg = await dm.send('.')
    except discord.errors.Forbidden as e:
        embed = discord.Embed(title='Missing DM Permission', 
                                description='You can only view your reminders in DMs. Please '\
                                            '[change your preferences]({:s}) and invoke this '\
                                            'command again.\n You can revert the changes later on.'.format(r'https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-'),
                                color=0xff0000)

        await ctx.send(embed=embed, hidden=True)
    
    await ctx.send('Have a look at your DMs to edit this reminder', hidden=True)
    await test_msg.delete()
    await _interval_stm(client, dm, reminder)
