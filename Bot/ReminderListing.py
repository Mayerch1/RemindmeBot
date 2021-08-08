import asyncio
import math
from enum import Enum
import random
from unidecode import unidecode

import discord
from discord.ext import commands, tasks

from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Reminder import Reminder, IntervalReminder
import lib.input_parser
import lib.ReminderRepeater

class ReminderListing(commands.Cog):
    class STM():
        def __init__(self):
            self.page = 0
            self.dm = None
            self.scope = None
            self.menu_msg = None
            self.tz_str = None
            self.navigation_rows = []
            self.reminders = []


    def __init__(self, client):
        self.client = client


    # =====================
    # events functions
    # =====================

    @commands.Cog.listener()
    async def on_ready(self):
        print('ReminderListing loaded')

    # =====================
    # helper methods
    # =====================

 

    @staticmethod
    def _create_reminder_list(reminders):
        """convert the inputed reminder list
           into a menu-string, with leading emojis

        Args:
            reminders ([]]): list of reminders

        Returns:
            str: reminder list string
        """
        out_str = 'Sorted by date\n\n'

        for i, r in enumerate(reminders):
            out_str += lib.input_parser.num_to_emoji(i + 1)
            out_str += f' {r.msg[0:50]}\n'

        return out_str

    @staticmethod
    def get_reminder_list_eb(reminders, page):
        """get the menu embed for all reminders
           in respect to the selected page

        Args:
            reminders ([]]): reminder list
            page (int): selected page

        Returns:
            discord.Embed: the menu embed
        """

        page_cnt = math.ceil(len(reminders) / 9)
        selectables = ReminderListing.get_reminders_on_page(reminders, page)

        out_str = ReminderListing._create_reminder_list(selectables)

        embed = discord.Embed(title=f'List of reminders {page+1}/{page_cnt}',
                                description=out_str)
        return embed

    @staticmethod
    def get_reminders_on_page(reminders, page):
        """select the reminders which are
           present on the selected page

        Args:
            reminders ([]): list of reminders
            page (int): selected page

        Returns:
            []: list of reminders on page
        """
        
        from_idx = page*9
        # the reminders are selected with a:b syntax
        # which is not inclusive for b
        to_idx = (page*9) + 9
        to_idx = min(to_idx, len(reminders))

        return reminders[from_idx:to_idx]

 

    # =====================
    # stm core
    # =====================

    async def _exit_stm(self, stm):
        """exit the stm, disable all components
           and send a goodbye message

        Args:
            stm (STM): stm object
        """
        await stm.dm.send('If you wish to edit more reminders, re-invoke the command')
        
        for n_row in stm.navigation_rows:
            for c in n_row['components']:
                c['disabled'] = True

        try:
            await stm.menu_msg.edit(components=[*stm.navigation_rows])
        except AttributeError:
            # if the stm exits outside the basic menu, nothing to be done 
            # here
            pass



    async def update_navigation(self, stm: STM, push_update=False):
        """update the navigation and selection row
           to show the available reminders in the dropdown

           the message is only updated on push_update
        """

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.secondary,
                emoji='⏪',
                custom_id='reminder_list_navigation_prev'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                emoji='⏩',
                custom_id='reminder_list_navigation_next'
            )
        ]
        stm.navigation_rows = [manage_components.create_actionrow(*buttons)]


        selectables = ReminderListing.get_reminders_on_page(stm.reminders, stm.page)

        if selectables:
            reminder_options = [manage_components.create_select_option(
                                    label= unidecode(r.msg)[:25] or '*empty reminder*', 
                                    emoji= lib.input_parser.num_to_emoji(i+1), 
                                    value= str(i))
                                    for i, r in enumerate(selectables)]

            reminder_selection = (
                manage_components.create_select(
                    custom_id='reminder_list_reminder_selection',
                    placeholder='Select a reminder to edit',
                    min_values=1,
                    max_values=1,
                    options=reminder_options
                )
            )

            stm.navigation_rows.append(manage_components.create_actionrow(reminder_selection))

        if stm.menu_msg and push_update:
            await stm.question_msg.edit(components=[*stm.navigation_rows])


    async def update_message(self, stm, re_send=False):
        """update the message with the newest components
           and the current stm.reminders          

        Args:
            stm ([type]): [description]
            re_send (bool, optional): will re-send the entire message
                                      instead of updating the existing msg
        """

        if re_send or not stm.menu_msg:
            if stm.menu_msg:
                await stm.menu_msg.delete()
            stm.menu_msg = await stm.dm.send(content='...')

        eb = ReminderListing.get_reminder_list_eb(stm.reminders, stm.page)
        await stm.menu_msg.edit(content='', embed=eb, components=[*stm.navigation_rows])


    async def process_navigation(self, ctx, stm):
        """advance the menu page in respect to 
           page limits, handles wrap-around
        """

        if ctx.custom_id == 'reminder_list_navigation_prev':
            stm.page -= 1
        elif ctx.custom_id == 'reminder_list_navigation_next':
            stm.page += 1

        page_cnt = math.ceil(len(stm.reminders) / 9)

        if stm.page < 0:
            stm.page = page_cnt - 1
        elif stm.page >= page_cnt:
            stm.page = 0

        await ctx.defer(edit_origin=True)


    async def process_reminder_edit(self, ctx, stm):
        """called on selection event of component
           shows options (currently only delete)
           for the selected reminder

        Args:
            ctx (ComponentContext): update event
            stm ([type]): [description]
        """

        resend_menu = False

        sel_id = ctx.selected_options[0]
        sel_id = int(sel_id)  # must be integer

        # update reminders
        # in case some of them have elapsed
        
        stm.reminders = Connector.get_scoped_reminders(stm.scope)

        reminders = ReminderListing.get_reminders_on_page(stm.reminders, stm.page)

        if sel_id >= len(reminders):
            return # a reminder elapsed since selection

        reminder = reminders[sel_id]

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.secondary,
                label='Return ',
                custom_id='reminderlist_edit_return'
            ),
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Set Interval',
                custom_id='reminderlist_edit_interval',
                emoji='🔁'
            ),
            manage_components.create_button(
                style=ButtonStyle.danger,
                label='Delete',
                custom_id='reminderlist_edit_delete'
            )
        ]

        action_row = manage_components.create_actionrow(*buttons)
        await ctx.edit_origin(embed=reminder.get_info_embed(stm.tz_str), components=[action_row])
        

        try:
            delete_ctx = await manage_components.wait_for_component(self.client, components=action_row, timeout=5*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            return
        
        await delete_ctx.defer(edit_origin=True)

        # delete the reminder
        # return to main menu in any case
        if delete_ctx.custom_id == 'reminderlist_edit_delete':
            if isinstance(reminder, IntervalReminder):
                Connector.delete_interval(reminder._id)
            else:
                Connector.delete_reminder(reminder._id)
        elif delete_ctx.custom_id == 'reminderlist_edit_interval':
            await lib.ReminderRepeater.transfer_interval_setup(self.client, stm, reminder)
            resend_menu = True

        return resend_menu


    async def reminder_stm(self, stm):

        stm.page = 0

        # for first iteration, the menu message is already up to date
        re_send_menu = False

        while True:
            # always update here, as a reminder could've been elapsed since last iteration
            stm.reminders = Connector.get_scoped_reminders(stm.scope)
            if not stm.reminders:
                await stm.dm.send('```No further reminders for this instance```')
                await self._exit_stm(stm)
                return

            await self.update_navigation(stm, push_update=False)
            await self.update_message(stm, re_send=re_send_menu)
            re_send_menu = False

            try:
                comp_ctx = await manage_components.wait_for_component(self.client, components=[*stm.navigation_rows], timeout=10*60)
            except asyncio.exceptions.TimeoutError:
                await self._exit_stm(stm)
                return

            if comp_ctx.custom_id.startswith('reminder_list_navigation'):
                await self.process_navigation(comp_ctx, stm)
            elif comp_ctx.custom_id == 'reminder_list_reminder_selection':
                re_send_menu = await self.process_reminder_edit(comp_ctx, stm)

    # =====================
    # intro methods
    # =====================

    async def send_intro_dm(self, ctx, intro_embed):
        """create a dm with the user and ack the ctx (with hint to look at DMs)
           if DM creation fails, send an error embed instead

        Args:
            ctx ([type]): [description]
            intro_message ([type]): [description]

        Returns:
            DM: messeagable, None if creation failed 
        """

        dm = await ctx.author.create_dm()

        try:
            await dm.send(embed=intro_embed)
        except discord.errors.Forbidden as e:
            embed = discord.Embed(title='Missing DM Permission', 
                                    description='You can only view your reminders in DMs. Please '\
                                                '[change your preferences]({:s}) and invoke this '\
                                                'command again.\n You can revert the changes later on.'.format(r'https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-'),
                                    color=0xff0000)

            await ctx.send(embed=embed, hidden=True)
            return None

        await ctx.send('Please have a look at your DMs', hidden=True)
        return dm


    async def show_private_reminders(self, ctx):
        """create a dm with the user and ack the ctx

        Args:
            ctx ([type]): [description]
            intro_message ([type]): [description]

        Returns:
            DM: messeagable, None if creation failed 
        """

        # only used for debug print
        session_id = random.randint(1e3, 1e12)
        print('starting private dm session ' + str(session_id))


        intro_eb = discord.Embed(title=f'Private Reminder list', 
                                description='You requested to see all reminders created by you.\n'\
                                        'Keep in mind that the following list will only show reminders that are not related to any server.\n'\
                                        'You need to invoke this command for every server you have setup further reminders.')
    
        dm = await self.send_intro_dm(ctx, intro_eb)

        if not dm:
            return


        scope = Connector.Scope(is_private=True, user_id=ctx.author.id)

        stm = ReminderListing.STM()
        stm.scope = scope
        stm.dm = dm
        stm.tz_str = Connector.get_timezone(ctx.author.id)

        await self.reminder_stm(stm)
        

        print('ending dm session ' + str(session_id))


    async def show_reminders_dm(self, ctx):

        # only used for debug print
        session_id = random.randint(1e3, 1e12)
        print('starting dm session ' + str(session_id))
        
        intro_eb = discord.Embed(title=f'Reminder list for {ctx.guild.name}', 
                            description='You requested to see all reminders created by you.\n'\
                                        'Keep in mind that the following list will only show reminders related to the server `{:s}`.\n'\
                                        'You need to invoke this command for every server you have setup further reminders.'.format(ctx.guild.name))
        
        dm = await self.send_intro_dm(ctx, intro_eb)

        if not dm:
            return

        scope = Connector.Scope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)

        stm = ReminderListing.STM()
        stm.scope = scope
        stm.dm = dm
        stm.tz_str = Connector.get_timezone(ctx.guild.id)

        await self.reminder_stm(stm)

        print('ending dm session ' + str(session_id))


    # =====================
    # commands functions
    # =====================

    @cog_ext.cog_slash(name='reminder_list', description='List all reminders created by you')
    async def reminder_list(self, ctx):

        if ctx.guild:
            await self.show_reminders_dm(ctx)
        else:
            await self.show_private_reminders(ctx)


def setup(client):
    client.add_cog(ReminderListing(client))