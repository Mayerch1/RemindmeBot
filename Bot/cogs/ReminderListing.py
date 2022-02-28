import asyncio
import logging
import math
from enum import Enum
import random
from unidecode import unidecode
from dateutil import tz

import discord
from discord.ext import commands, tasks

from lib.Connector import Connector
from lib.Reminder import Reminder, IntervalReminder
import lib.input_parser

import util.interaction
import util.reminderInteraction
import util.formatting
#import lib.ReminderRepeater

from lib.Analytics import Analytics, Types

log = logging.getLogger('Remindme.Listing')



class STMState(Enum):
        INIT=0

class STM():
    def __init__(self, ctx, scope):
        self.ctx: discord.ApplicationContext=ctx
        self.scope:Connector.Scope=scope
        self.state:STMState = STMState.INIT
        self.page:int=0
        self.reminders:list[Reminder] = []

        self.menu_msg = None
        self.tz_str = None
        self.navigation_rows = []
        self.roles = []



class ReminderListView(util.interaction.CustomView):
    def __init__(self, stm, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stm:STM = stm
        self.update_dropdown()

    def get_embed(self) -> discord.Embed:
    
        if self.stm.scope.is_private:
            title_str = f'**Private** Reminder list'
        else:
            title_str = f'Reminder list for {self.stm.ctx.guild.name}'        
        footer_str = 'You only see reminders of the server this command was invoked on'

        eb = ReminderListing.get_reminder_list_eb(self.stm.reminders, self.stm.page, title_str, self.stm.tz_str)
        eb.set_footer(text=footer_str)
        return eb

    
    def get_reminders_on_page(self, reminders, page):
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


    def update_dropdown(self):
        self.stm.reminders = Connector.get_scoped_reminders(self.stm.scope)
        page_rems = self.get_reminders_on_page(self.stm.reminders, self.stm.page)

        if page_rems:
            reminder_options = [discord.SelectOption(
                                        label= unidecode(r.msg)[:25] or '*empty reminder*', 
                                        emoji= lib.input_parser.num_to_emoji(i+1), 
                                        value= str(i))
                                        for i, r in enumerate(page_rems)]
            dd = discord.ui.Select(
                placeholder='Select a reminder to edit',
                min_values=0,
                max_values=1,
                options=reminder_options
            )
            dd.callback = self.dropdown_callback

            # delete old selects
            old_sel = [x for x in self.children if isinstance(x, discord.ui.Select)]
            if old_sel:
                self.children.remove(old_sel[0])
            self.add_item(dd)



    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.secondary)
    async def prev_page(self, button:  discord.ui.Button, interaction: discord.Interaction):
        self.stm.page -= 1
        page_cnt = math.ceil(len(self.stm.reminders) / 9)

        if self.stm.page < 0:
            self.stm.page = page_cnt-1

        new_eb = self.get_embed()
        self.update_dropdown()
        await interaction.response.edit_message(embed=new_eb, view=self)



    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.secondary)
    async def next_page(self, button:  discord.ui.Button, interaction: discord.Interaction):
        self.stm.page += 1
        page_cnt = math.ceil(len(self.stm.reminders) / 9)

        if self.stm.page >= page_cnt:
            self.stm.page = 0

        new_eb = self.get_embed()
        self.update_dropdown()
        await interaction.response.edit_message(embed=new_eb, view=self)



    async def dropdown_callback(self, interaction: discord.Interaction):
        

        # do not update reminder list
        # otherwise the user selected reminder could be another one than the actual one
        page_rems = self.get_reminders_on_page(self.stm.reminders, self.stm.page)
        sel = interaction.data['values'][0] # min_select 1
        

        if int(sel) >= len(page_rems):
            # list is not long enough anymore
            # update ui to show shorter list
            new_eb = self.get_embed()
            self.update_dropdown()
            await interaction.edit_original_message(embed=new_eb, view=self) # already responded
            return


        # go ahead with reminder edit
        sel_rem = page_rems[int(sel)]
        view = util.reminderInteraction.ReminderEditView(sel_rem, self.stm, message=self.message)
        rem_embed = view.get_embed()
        await interaction.response.edit_message(embed=rem_embed, view=view)

        await view.wait()
        self.message = view.message # update in case it was transferred

        # update reminder list and dropdown
        self.stm.reminders = Connector.get_scoped_reminders(self.stm.scope)
        self.update_dropdown()
        new_eb = self.get_embed()
        await self.message.edit_original_message(embed=new_eb, view=self) # already responded
        # self is not used anymore, until this is finished




class ReminderListing(commands.Cog):
    def __init__(self, client):
        self.client = client


    # =====================
    # events functions
    # =====================

    @discord.Cog.listener()
    async def on_ready(self):
        log.info('ReminderListing loaded')

    # =====================
    # helper methods
    # =====================

    

    @staticmethod
    def _create_reminder_list(reminders, tz_str):
        """convert the inputed reminder list
           into a menu-string, with leading emojis

        Args:
            reminders ([]]): list of reminders

        Returns:
            str: reminder list string
        """
        out_str = 'Sorted by date\n\n'

        rows = []
        for i, r in enumerate(reminders):

            MAX_FIELD_LEN = 33
            MAX_MSG_LEN = 26

            at_local = r.at.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str))

            # a total of 33 chars are possible before overflow
            #
            # the message will get up to 26 chars
            # the channel len will get the rest, but at least 7
            max_ch_len = MAX_FIELD_LEN-min(len(r.msg), MAX_MSG_LEN)
            
            rows.append((str(i+1)+'.',
                        at_local.strftime('%d.%b %H:%M'),
                        (r.ch_name or 'Unknown')[0:max_ch_len],
                        r.msg[0:MAX_MSG_LEN]))

        table = util.formatting.generate_code_table(['No.', 'Next', 'Channel', 'Message'], rows, description='Given in your server timezone')

        return '\n'.join(table)


    @staticmethod
    def get_reminder_list_eb(reminders: list[Reminder], page, title_start='Reminder list', tz_str='UTC'):
        """get the menu embed for all reminders
           in respect to the selected page

           if title_start is specified, will onld add page counter
           at end of title_start

        Args:
            reminders ([]]): reminder list
            page (int): selected page

        Returns:
            discord.Embed: the menu embed
        """

        page_cnt = math.ceil(len(reminders) / 9)
        selectables = ReminderListing.get_reminders_on_page(reminders, page)

        out_str = ReminderListing._create_reminder_list(selectables, tz_str)

        embed = discord.Embed(title=f'{title_start} {page+1}/{min(page_cnt, 1)}',
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




    async def process_channel_selector(self, ctx, stm, reminder):
        
        guild = self.client.get_guild(reminder.g_id)
        if not guild:
            await util.interaction.show_error_ack(self.client, ctx, 
                                      'Failed to edit Reminder', 
                                      'Couldn\'t resolve the server of the selected reminder', 
                                      edit_origin=True)
            return

        txt_channels = list(filter(lambda ch: isinstance(ch, discord.TextChannel), guild.channels))
        txt_channels = txt_channels[0:25]  # discord limitation of selectables
        
        if not txt_channels:
            await util.interaction.show_error_ack(self.client, ctx, 
                                      'Failed to edit Reminder', 
                                      'Couldn\'t find any text channels. This could be caused by missing permissions on the server.', 
                                      edit_origin=True)
            return

        channel_options = [manage_components.create_select_option(
                                    label= unidecode(r.name)[:25] or '*unknown channel*', 
                                    value= str(r.id))
                                    for i, r in enumerate(txt_channels)]
        reminder_selection = (
            manage_components.create_select(
                custom_id='reminder_edit_channel_selection',
                placeholder='Select a new channel',
                min_values=1,
                max_values=1,
                options=channel_options
            )
        )
        action_rows = [manage_components.create_actionrow(reminder_selection)]

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.red,
                label='Cancel',
                custom_id='reminderlist_edit_cancel'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        # already deferred
        await ctx.edit_origin(components=action_rows)


        accepted_ack = False
        while not accepted_ack:
            try:
                edit_ctx = await manage_components.wait_for_component(self.client, components=action_rows, timeout=5*60)
            except asyncio.exceptions.TimeoutError:
                # abort channel edit
                return
            
            if edit_ctx.component_id == 'reminderlist_edit_cancel':
                try:
                    await edit_ctx.defer(edit_origin=True)
                except discord.NotFound:
                    accepted_ack = False
                else:
                    return
            else:
                # following flow will handle 
                # NotFound errors
                accepted_ack = True

        # bot could resolve channel before (when offering drop-down)
        # therefore channel should be available again
        sel_channel_id = int(edit_ctx.selected_options[0])
        sel_channel = self.client.get_channel(sel_channel_id)
        
        if not sel_channel:
            await util.interaction.show_error_ack(self.client, edit_ctx, 
                                      'Failed to edit Reminder', 
                                      'Couldn\'t resolve the selected channel. It might have been deleted since the previous message was send.', 
                                      edit_origin=True)
            return
        
        success = Connector.set_reminder_channel(reminder._id, sel_channel_id)
        if not success:
            await util.interaction.show_error_ack(self.client, edit_ctx, 
                                      'Failed to edit Reminder', 
                                      'The database access failed, please contact the developers (`/help`) to report this bug.', 
                                      edit_origin=True)
            return

        
        
        await util.interaction.show_success_ack(self.client, edit_ctx,
                                    'New Notification Channel',
                                    f'This reminder will now be delivered to `{sel_channel.name}`.\nMake sure this bot has permission to send messages into that channel, otherwise the reminder might not be delivered',
                                    edit_origin=True)




    async def reminder_stm(self, stm: STM):
        # first fetch of reminders
        stm.reminders = Connector.get_scoped_reminders(stm.scope)

        # manually send initial message to init view
        view = ReminderListView(stm)
        eb = view.get_embed()    
        view.message = await stm.ctx.respond(embed=eb, view=view, ephemeral=True)


    # =====================
    # intro methods
    # =====================

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
        log.debug('starting private dm session ' + str(session_id))

        scope = Connector.Scope(is_private=True, user_id=ctx.author.id)
        stm = STM(ctx=ctx, scope=scope)
        stm.tz_str = Connector.get_timezone(ctx.author.id)

        await self.reminder_stm(stm)
        print('ending dm session ' + str(session_id))


    async def show_server_reminders(self, ctx):

        # only used for debug print
        session_id = random.randint(1e3, 1e12)
        log.debug('starting dm session ' + str(session_id))

        scope = Connector.Scope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)
        stm = STM(ctx=ctx, scope=scope)
        stm.tz_str = Connector.get_timezone(ctx.guild.id)
        stm.roles = ctx.author.roles

        await self.reminder_stm(stm)
        print('ending dm session ' + str(session_id))


    # =====================
    # commands functions
    # =====================

    @commands.slash_command(name='reminder_list', description='List all reminders created by you', guild_ids=[140150091607441408])
    async def reminder_list(self, ctx):

        if ctx.guild:
            await self.show_server_reminders(ctx)
        else:
            await self.show_private_reminders(ctx)

def setup(client):
    client.add_cog(ReminderListing(client))