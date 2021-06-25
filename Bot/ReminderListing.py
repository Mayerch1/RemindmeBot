import asyncio
import math
from enum import Enum
import random

import discord
from discord.ext import commands, tasks

from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Reminder import Reminder
import lib.input_parser

class ReminderListing(commands.Cog):

    class ListingScope:
        def __init__(self, is_private=False, guild_id=None, user_id=None):
            self.is_private = is_private
            self.guild_id = guild_id
            self.user_id = user_id


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

    def _get_reminders(self, scope: ListingScope):

        rems = []

        if scope.is_private and scope.user_id:
            rems =  Connector.get_user_private_reminders(scope.user_id)
        elif scope.user_id and scope.guild_id:
            rems =  Connector.get_user_reminders(scope.guild_id, scope.user_id)
        else:
            rems = []

        return sorted(rems, key=lambda r: r.at)


    @staticmethod
    def _create_reminder_list(reminders, from_idx, to_idx):
        out_str = 'Sorted by date\n\n'
        to_idx = min(to_idx, len(reminders) - 1)

        for i in range(from_idx, to_idx + 1):
            out_str += lib.input_parser.num_to_emoji((i-from_idx) + 1)
            out_str += f' {reminders[i].msg[0:50]}\n'

        return out_str, (to_idx - from_idx)

    
    @staticmethod
    def _get_reminder_list_eb(reminders, page):
        page_cnt = math.ceil(len(reminders) / 9)
        out_str, count = ReminderListing._create_reminder_list(reminders, (page * 9), (page * 9) + 8)

        embed = discord.Embed(title=f'List of reminders {page+1}/{page_cnt}',
                                description=out_str)

        return embed


    @staticmethod
    def _get_reminder_cnt_on_page(reminders, page):

        if len(reminders)==0:
            return 0  # special case to make calculation easier

        from_idx = page*9
        to_idx = from_idx + 8

        from_idx = min(from_idx, len(reminders) - 1)
        to_idx = min(to_idx, len(reminders) - 1)

        return (to_idx - from_idx) + 1


    @staticmethod
    def _index_to_reminder(reminders, page, index):
        """converts a page index into an absolute list index
           and returns the appropriate reminder

        Args:
           page (int) - page index, 0-offset
           index (int) - index of page, 1-offset

        Returns:
            reminder - None if index out of range
        """

        access_idx = index + (page * 9) - 1

        if access_idx >= len(reminders) or access_idx < 0:
            return None  # out of range
        else:
            return reminders[access_idx]


    # =====================
    # stm core
    # =====================


    async def _setup_stm(self, dm, reminders):

        if len(reminders) == 0:
            await dm.send('```No reminders for this instance```')
            return None, None

        buttons = [
            manage_components.create_button(
                style=ButtonStyle.primary,
                label="Select Reminder",
                custom_id='select_reminder'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                emoji='⏪',
                custom_id='navigation_prev'
            ),
            manage_components.create_button(
                style=ButtonStyle.secondary,
                emoji='⏩',
                custom_id='navigation_next'
            )
        ]

        action_row = manage_components.create_actionrow(*buttons)
        msg = await dm.send(embed=ReminderListing._get_reminder_list_eb(reminders, 0), components=[action_row])

        return msg, action_row

    
    async def _exit_stm(self, dm, msg, component):
        
        for c in component['components']:
            c['disabled'] = True

        await msg.edit(components=[component])
        pass



    async def update_reminder_embed(self, ctx, reminders, page):
        eb = ReminderListing._get_reminder_list_eb(reminders, page)
        await ctx.edit_origin(embed=eb)


    async def delete_reminder(self, ctx, reminder):
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Go Back'
            ),
            manage_components.create_button(
                style=ButtonStyle.danger,
                label='Delete'
            )
        ]

        action_row = manage_components.create_actionrow(*buttons)
        await ctx.edit_origin(embed=reminder.get_info_embed(), components=[action_row])
        
        delete_ctx = await manage_components.wait_for_component(self.client, components=action_row)
        await delete_ctx.defer(edit_origin=True)

        # delete the reminder
        # return to main menu in any case
        if delete_ctx.component.get('label', None) == 'Delete':
            Connector.delete_reminder(reminder._id)

        return delete_ctx


    async def select_reminder(self, ctx, reminders, page):

        rem_cnt = ReminderListing._get_reminder_cnt_on_page(reminders, page)

        buttons = [ manage_components.create_button(style=ButtonStyle.secondary, label=str(i+1)) for i in range(rem_cnt)]
        buttons.append(
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Go Back'
            )
        )

        components = [manage_components.create_actionrow(*buttons[0:5]),]
        if buttons[5:]:
            components.append(manage_components.create_actionrow(*buttons[5:]))

        await ctx.edit_origin(components=components)

        selection_ctx = await manage_components.wait_for_component(self.client, components=components)
        label = selection_ctx.component.get('label', None)

        try:
            idx = int(label) # keep 1-offset
        except ValueError:
            idx = None

        if idx is None:
            return selection_ctx

        rem = ReminderListing._index_to_reminder(reminders, page, idx)
        if not rem:
            return selection_ctx

        # sohw delete prompt
        # return to menue in any case
        return await self.delete_reminder(selection_ctx, rem)



    async def reminder_stm(self, scope, dm):
        page = 0

        reminders = self._get_reminders(scope)
        msg, navigation_comp = await self._setup_stm(dm, reminders)

        if not msg:
            return

        while True:

            try:
                button_ctx = await manage_components.wait_for_component(self.client, components=navigation_comp, timeout=120)
            except asyncio.exceptions.TimeoutError:
                await self._exit_stm(dm, msg, navigation_comp)
                return

            reminders = self._get_reminders(scope)
            page_cnt = math.ceil(len(reminders) / 9)


            if button_ctx.component_id == 'select_reminder':
                return_ctx = await self.select_reminder(button_ctx, reminders, page)
                reminders = self._get_reminders(scope)
                await return_ctx.edit_origin(embed=ReminderListing._get_reminder_list_eb(reminders, page), components=[navigation_comp]) # restore menu

                if len(reminders) == 0:
                    await self._exit_stm(dm, msg, navigation_comp)
                    return
            else:
                if button_ctx.component_id == 'navigation_prev':
                    page += 1
                    
                elif button_ctx.component_id == 'navigation_next':
                    page -= 1
                else:
                    continue # no match
                
                if page < 0:
                    page = page_cnt - 1
                elif page >= page_cnt:
                    page = 0 
                await self.update_reminder_embed(button_ctx, reminders, page)
            


    # =====================
    # intro methods
    # =====================

    async def send_intro_dm(self, ctx, intro_message):
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
            await dm.send(intro_message)
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

        # only used for debug print
        session_id = random.randint(1e3, 1e12)
        print('starting private dm session ' + str(session_id))
        
        intro_msg = 'You requested to see all reminders created by you.\n'\
                        'Keep in mind that the following list will only show reminders that are not related to any server.\n'\
                        'You need to invoke this command for every server you have setup further reminders.'
            
        dm = await self.send_intro_dm(ctx, intro_msg)

        if not dm:
            return

        scope = ReminderListing.ListingScope(is_private=True, user_id=ctx.author.id)

        await self.reminder_stm(scope, dm)
        await dm.send('If you wish to edit more reminders, re-invoke the command')

        print('ending dm session ' + str(session_id))


    async def show_reminders_dm(self, ctx):

        # only used for debug print
        session_id = random.randint(1e3, 1e12)
        print('starting dm session ' + str(session_id))
        
        intro_msg = 'You requested to see all reminders created by you.\n'\
                        'Keep in mind that the following list will only show reminders related to the server `{:s}`.\n'\
                        'You need to invoke this command for every server you have setup further reminders.'.format(ctx.guild.name)
            
        dm = await self.send_intro_dm(ctx, intro_msg)

        if not dm:
            return

        scope = ReminderListing.ListingScope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)

        await self.reminder_stm(scope, dm)
        await dm.send('If you wish to edit more reminders, re-invoke the command')

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