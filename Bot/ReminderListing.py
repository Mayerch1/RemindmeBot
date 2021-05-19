import asyncio
import math
from enum import Enum

import discord
from discord.ext import commands, tasks

from lib.Connector import Connector
from lib.Reminder import Reminder
import lib.input_parser

class ReminderListing:

    class ListingScope:
        def __init__(self, is_private=False, guild_id=None, user_id=None):
            self.is_private = is_private
            self.guild_id = guild_id
            self.user_id = user_id

    _client = None

    @staticmethod
    def _get_reminders(scope: ListingScope):

        rems = []

        if scope.is_private and scope.user_id:
            rems =  Connector.get_user_private_reminders(scope.user_id)
        elif scope.user_id and scope.guild_id:
            rems =  Connector.get_user_reminders(scope.guild_id, scope.user_id)
        else:
            rems = []

        return sorted(rems, key=lambda r: r.at)


    @staticmethod
    async def _edit_reminder(dm, reminders, page, chosen):

        idx = chosen + (page * 9) - 1

        if idx >= len(reminders) or idx < 0:
            await dm.send('Index out of range')
            return

        rem = reminders[idx]

        msg =await dm.send(embed = (rem.get_info_embed()))
        await msg.add_reaction('✅')
        await msg.add_reaction('🗑️')

        def react_check(reaction):
            return reaction.message_id == msg.id and \
                        dm.recipient.id == reaction.user_id and \
                        (reaction.emoji.name == '🗑️' or reaction.emoji.name == '✅')

        try:
            reaction = await ReminderListing._client.wait_for('raw_reaction_add', check=react_check, timeout=45.0)
        except asyncio.exceptions.TimeoutError:
            await msg.add_reaction('⏲')
            return
        
        # delete the reminder, only on bin
        # other emojis continue with reminder management
        if reaction.emoji.name == '🗑️':
            Connector.delete_reminder(rem._id)


    @staticmethod
    async def _create_reminder_list(reminders, from_idx, to_idx):
        out_str = 'Sorted by date\n\n'
        to_idx = min(to_idx, len(reminders) - 1)

        for i in range(from_idx, to_idx + 1):
            out_str += lib.input_parser.num_to_emoji((i-from_idx) + 1)
            out_str += f' {reminders[i].msg[0:50]}\n'

        return out_str, (to_idx - from_idx)


    @staticmethod
    async def _handle_page(dm, reminders, page):
        page_cnt = math.ceil(len(reminders) / 9)

        out_str, count = await ReminderListing._create_reminder_list(reminders, (page * 9), (page * 9) + 8)
        embed = discord.Embed(title=f'List of reminders {page+1}/{page_cnt}',
                                description=out_str)

        msg = await dm.send(embed=embed)
        await msg.add_reaction('⏪')
        await msg.add_reaction('⏩')
        await msg.add_reaction('❌')
        await dm.send('Type the number of the reminder to see more details')

        return msg.id


    @staticmethod
    async def _reminder_stm(scope, dm):
        page = 0

        while True:

            reminders = ReminderListing._get_reminders(scope)
            if len(reminders) == 0:
                await dm.send('```No reminders for this instance```')
                return

            page_cnt = math.ceil(len(reminders) / 9)
            

            if page < 0:
                page = page_cnt - 1
            elif page >= page_cnt:
                page = 0 

            msg_id = await ReminderListing._handle_page(dm, reminders, page)

            def react_check(reaction):
                return reaction.message_id == msg_id and \
                        dm.recipient.id == reaction.user_id and \
                        (reaction.emoji.name == '⏩' or reaction.emoji.name == '⏪' or reaction.emoji.name == '❌')
                        
            def msg_check(msg):
                return msg.author.id == dm.recipient.id and msg.channel.id == dm.id

            pending_tasks = [ReminderListing._client.wait_for('raw_reaction_add',check=react_check, timeout=60),
                            ReminderListing._client.wait_for('message',check=msg_check, timeout=60)]

            done_tasks, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)

            # cancel the failed tasks
            for task in pending_tasks:
                task.cancel()

            # only process the first 'done' task
            # ignore any potential secondary tasks
            # if no tasks, abort the cycle (timeout)
            if not done_tasks:
                return

            first_task = done_tasks.pop()
            ex = first_task.exception()

            if ex:
                # any exception is handled the same way as a timeout exception
                return

            result = await first_task

            if isinstance(result, discord.RawReactionActionEvent):
                if result.emoji.name == '⏩':
                    page += 1
                elif result.emoji.name == '⏪':
                    page -= 1
                else:
                    return
                # other options not possible

            elif isinstance(result, discord.Message):
                chosen = lib.input_parser._to_int(result.content)
                if chosen:
                    await ReminderListing._edit_reminder(dm, reminders, page, chosen)
                else:
                    await dm.send('Please enter a positive number')
            else:
                # ignore other events, fail the stm
                return


    @staticmethod
    async def _send_intro_dm(ctx, intro_message):
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


    @staticmethod
    async def show_private_reminders(client, ctx):

        ReminderListing._client = client
        
        intro_msg = 'You requested to see all reminders created by you.\n'\
                        'Keep in mind that the following list will only show reminders that are not related to any server.\n'\
                        'You need to invoke this command for every server you have setup further reminders.'
            
        dm = await ReminderListing._send_intro_dm(ctx, intro_msg)

        if not dm:
            return


        scope = ReminderListing.ListingScope(is_private=True, user_id=ctx.author.id)
        await ReminderListing._reminder_stm(scope, dm)
        await dm.send('If you wish to edit more reminders, re-invoke the command')


    @staticmethod
    async def show_reminders_dm(client, ctx):

        ReminderListing._client = client
        
        intro_msg = 'You requested to see all reminders created by you.\n'\
                        'Keep in mind that the following list will only show reminders related to the server `{:s}`.\n'\
                        'You need to invoke this command for every server you have setup further reminders.'.format(ctx.guild.name)
            
        dm = await ReminderListing._send_intro_dm(ctx, intro_msg)

        if not dm:
            return


        scope = ReminderListing.ListingScope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)

        await ReminderListing._reminder_stm(scope, dm)
        await dm.send('If you wish to edit more reminders, re-invoke the command')
