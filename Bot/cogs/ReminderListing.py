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



class ReminderListView(util.interaction.CustomView):
    def __init__(self, stm, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stm:util.reminderInteraction.STM = stm
        self.update_dropdown()

    def get_embed(self) -> discord.Embed:
    
        if self.stm.scope.is_private:
            title_str = f'**Private** Reminder list'
        else:
            title_str = f'Reminder list for {self.stm.ctx.guild.name}'        
        footer_str = 'Reminders marked with * belong to other users'

        eb = ReminderListing.get_reminder_list_eb(self.stm.reminders, self.stm.page, title_str, self.stm.tz_str, self.stm.scope.user_id)
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
        roles = self.stm.ctx.author.roles if self.stm.scope.guild_id else []
        self.stm.reminders = Connector.get_guild_reminders(self.stm.scope, roles)
        page_rems = self.get_reminders_on_page(self.stm.reminders, self.stm.page)

        if(len(page_rems) > 25):
            # TODO: debug issue?
            log.warning('too many elements in dropdown in update_dropdown/ReminderListing.py')
            page_rems = page_rems[0:25] # max 25 elements

        if page_rems:
            reminder_options = [discord.SelectOption(
                                        label= unidecode(r.title)[:25] if r.title else (unidecode(r.msg)[:25] or '*empty reminder*'), 
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
        roles = self.stm.ctx.author.roles if self.stm.scope.guild_id else []
        self.stm.reminders = Connector.get_guild_reminders(self.stm.scope, roles)
        self.update_dropdown()
        new_eb = self.get_embed()
        await view.open_interaction.response.edit_message(embed=new_eb, view=self) # already responded
        # self is not used anymore, until this is finished




class ReminderListing(commands.Cog):
    def __init__(self, client):
        self.client = client


    # =====================
    # events functions
    # =====================

    @discord.Cog.listener()
    async def on_ready(self):
        log.info('loaded')

    # =====================
    # helper methods
    # =====================

    

    @staticmethod
    def _create_reminder_list(reminders, tz_str, author_id=None):
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

            at_local = r.at.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str)) if r.at else None


            content = r.title[0:MAX_MSG_LEN] if r.title else r.msg[0:MAX_MSG_LEN]

            sfx = ''
            if author_id and r.author != author_id:
                sfx = '*'


            # a total of 33 chars are possible before overflow
            #
            # the message will get up to 26 chars
            # the channel len will get the rest, but at least 7
            max_ch_len = MAX_FIELD_LEN-min(len(content), MAX_MSG_LEN)
            
            rows.append((str(i+1)+'.'+sfx,
                        at_local.strftime('%d.%b %H:%M') if at_local else '-',
                        (r.ch_name or 'Unknown')[0:max_ch_len],
                        content))

        table = util.formatting.generate_code_table(['No.', 'Next', 'Channel', 'Message'], rows, description='Given in your server timezone')

        return '\n'.join(table)


    @staticmethod
    def get_reminder_list_eb(reminders: list[Reminder], page, title_start='Reminder list', tz_str='UTC', author_id=None):
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

        out_str = ReminderListing._create_reminder_list(selectables, tz_str, author_id=author_id)

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

    async def reminder_stm(self, stm: util.reminderInteraction.STM):
        # first fetch of reminders
        roles = stm.ctx.author.roles if stm.scope.guild_id else []
        stm.reminders = Connector.get_guild_reminders(stm.scope, roles)

        # manually send initial message to init view
        view = ReminderListView(stm)
        eb = view.get_embed()    
        view.message = await stm.ctx.respond(embed=eb, view=view, ephemeral=True)


    # =====================
    # commands functions
    # =====================

    @commands.slash_command(name='reminder_list', description='List all reminders created by you')
    async def reminder_list(self, ctx):

        if ctx.guild:
            scope = Connector.Scope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)
        else:
            scope = Connector.Scope(is_private=True, user_id=ctx.author.id)

        stm = util.reminderInteraction.STM(ctx=ctx, scope=scope)
        stm.tz_str = Connector.get_timezone(scope.instance_id)
        await self.reminder_stm(stm)

def setup(client):
    client.add_cog(ReminderListing(client))