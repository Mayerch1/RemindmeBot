import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from bson import ObjectId

import copy

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from datetime import datetime, timedelta

from lib.Connector import Connector
from lib.Reminder import Reminder
import lib.input_parser
import lib.ReminderRepeater

from lib.Analytics import Analytics
from ReminderListing import ReminderListing


class ReminderModule(commands.Cog):

    REMIND_FORMAT_HELP = '```'\
                'allowed absolutes are\n'\
                '\t• eoy - remind at end of year\n'\
                '\t• eom - remind at end of month\n'\
                '\t• eow - remind at end of working week (Friday night)\n'\
                '\t• eod - remind at end of day\n'\
                '\n'\
                'allowed intervals are\n'\
                '\t• y(ears)\n'\
                '\t• mo(nths)\n'\
                '\t• w(eeks)\n'\
                '\t• d(ays)\n'\
                '\t• h(ours)\n'\
                '\t• mi(ns)\n'\
                '\n'\
                'you can combine relative intervals like this\n'\
                '\t1y 1mo 2 days -5h\n'\
                '\n'\
                'iso-timestamps are supported\n'\
                '\tbe aware that specifying a timezone\n'\
                '\twill ignore the server timezone\n'\
                '\n'\
                'natural dates are supported, you can try different formats\n'\
                '\t• 5 jul, 5th july, july 5\n'\
                '\t• 23 sept at 3pm, 23 sept at 15:00\n'\
                '\t• 2050\n'\
                '\tNote: the parser uses day-first and year-least\n'\
                '\t      (01/02/21 -> 1st January 2021)\n'\
                '\n'\
                'examples:\n'\
                '\t/remindme 1y Hello future me\n'\
                '\t/remindme 2 h drink some water\n'\
                '\t/remindme 1w 2d hello there\n'\
                '\t/remindme 2021-09-02T12:25:00+02:00 iso is cool\n'\
                '\n'\
                '\t/remind @User 1 mon What\'s up\n'\
                '\t/remind @User 24 dec Merry Christmas\n'\
                '\t/remind @User eoy Happy new year\n'\
                '\n'\
                'the reminder can occur as much as 1 minute delayed```\n'\
                
    HELP_FOOTER = 'If you find a bug in the parser, please reach out to us.\n'\
                    'Contact details are at `Get Support` on [top.gg](https://top.gg/bot/831142367397412874)'\
                    ' or on [Github](https://github.com/Mayerch1/RemindmeBot)'


    @staticmethod
    def to_int(num_str: str, base: int=10):
        
        try:
            conv_int = int(num_str, base)
        except ValueError:
            conv_int = None
        finally:
            return conv_int
    

    # =====================
    # internal functions
    # =====================

    def __init__(self, client):
        self.client = client

        print('starting reminder event loops')
        self.check_pending_reminders.start()
        self.check_reminder_cnt.start()


    async def print_reminder_dm(self, rem: Reminder, err_msg=None):
        # fallback to dm
        # target must be resolved, otherwise dm cannot be created

        try:
            target = await self.client.fetch_user(rem.target)
        except discord.errors.NotFound:
            print(f'cannot find user {rem.target} for reminder DM fallback')
            return

        # dm if channel not existing anymor
        dm =  await target.create_dm()

        eb = await rem.get_embed(self.client, is_dm=True)
        
        # first fallback is string-only message
        # second fallback is dm to user
        # DM never requires user mention (DM itself is a ping)
        try:
            await dm.send(embed=eb)
            if err_msg:
                await dm.send(f'||{err_msg}||')
        except discord.errors.Forbidden:

            try:
                await dm.send(rem.get_string())
            except discord.errors.Forbidden:
                print(f'failed to send reminder as DM fallback')


    async def print_reminder(self, rem: Reminder):

        # reminder is a DM reminder
        if not rem.g_id:
            await self.print_reminder_dm(rem)
            return

        guild = self.client.get_guild(rem.g_id)
        channel = guild.get_channel(rem.ch_id)

        # no need to resolve author, target is sufficient

        if not channel:
            err = f'`You are receiving this dm, as the reminder channel on \'{guild.name}\' is not existing anymore.`'
            await self.print_reminder_dm(rem, err)
            return

        eb = await rem.get_embed(self.client)

        # first fallback is string-only message
        # second fallback is dm to user

        perms = channel.permissions_for(guild.me)

        if perms.send_messages and perms.embed_links:
            try:
                # embed does not hold user mention
                await channel.send(f'<@!{rem.target}>', embed=eb)
                return
            except discord.errors.Forbidden:
                pass


        if perms.send_messages:
            try:
                # string already holds user mention
                await channel.send(rem.get_string())
                return
            except discord.errors.Forbidden:
                pass

        err = f'`You are receiving this dm, as I do not have permission to send messages into the channel \'{channel.name}\' on \'{guild.name}\'.`'
        await self.print_reminder_dm(rem, err)


    @staticmethod
    def delta_to_str(delta):
            ret_str = ''
            secs = delta.total_seconds()

            hours, rem = divmod(secs, 3600)
            mins, secs = divmod(rem, 60)
            
            if hours > 48:
                return '{:d} days ({:02d} hours)'.format(int(hours/24), int(hours))
            elif hours > 0:
                return '{:02d} h {:02d} m'.format(int(hours), int(mins))
            else:
                return '{:d} minutes'.format(int(mins))


    async def process_reminder(self, ctx, author, target, period, message):

        if ctx.guild:
            tz_str = Connector.get_timezone(author.guild.id)

            # try and get the last message, for providing a jump link
            try:
                last_msg = await ctx.channel.history(limit=1).flatten()
            except:
                last_msg = None

            last_msg = last_msg[0] if last_msg else None
        else:
            tz_str = 'UTC'
            last_msg = None

        err = False

        utcnow = datetime.utcnow()
        remind_at, info = lib.input_parser.parse(period, utcnow, tz_str)

        interval = remind_at - utcnow
        if interval <= timedelta(hours=0):
            if info != '':
                out_str = f'```Parsing hints:\n{info}```\n'
            else:
                out_str = ''

            if interval == timedelta(hours=0):
                # only append full help on invalid strings
                # not on negative intervals
                out_str += ReminderModule.REMIND_FORMAT_HELP
            out_str += ReminderModule.HELP_FOOTER
            
            embed = discord.Embed(title='Failed to create the reminder', description=out_str)
            await ctx.send(embed=embed, hidden=True)
            Analytics.invalid_f_string()
            return

        await ctx.defer() # allow more headroom for response latency, before command fails
        rem = Reminder()

        if ctx.guild:
            rem.g_id = ctx.guild.id
            rem.ch_id = ctx.channel_id
        else:
            # command was called in DM
            rem.g_id = None
            rem.ch_id = None

        rem.msg = message
        rem.at = remind_at
        rem.author = author.id
        rem.target = target.id
        rem.created_at = utcnow
        rem.last_msg_id = last_msg.id if last_msg else None

        # the id is required in case the users wishes to abort
        rem_id = Connector.add_reminder(rem)

        if rem.author == rem.target:
            Analytics.add_self_reminder(rem)
        else:
            Analytics.add_foreign_reminder(rem)
        
        # convert reminder period to readable delta
        # convert utc date into readable local time (locality based on server settings)
        delta_str = ReminderModule.delta_to_str(remind_at-utcnow)
        if tz_str == 'UTC':
            # this workaround is required, as system uses german term for UTC
            at_str = remind_at.strftime('%Y/%m/%d %H:%M UTC')
        else:
            at_str = remind_at.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str)).strftime('%Y/%m/%d %H:%M %Z')

        if target == author:
            out_str = f'Reminding you in `{delta_str}` at `{at_str}`.'
        else:
             out_str = f'Reminding {target.name} in `{delta_str}` at `{at_str}`.'
      
        if (remind_at-utcnow) < timedelta(minutes=5):
            out_str += '\nBe aware that the reminder can be as much as 1 minute delayed'
        out_str += '\n\n**Note:** Use `/reminder_list` to convert this reminder into a repeating reminder'

        if info:
            out_str += f'\n```Parsing hints:\n{info}```'
        
        # create the button to delete this reminder
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Set Interval',
                custom_id=f'direct-interval_{rem_id}',
                emoji='🔁'
            ),
            manage_components.create_button(
                style=ButtonStyle.danger,
                label='Delete',
                emoji='🗑️',
                custom_id=f'direct-delete_{rem_id}'
            )
        ]
        action_row = manage_components.create_actionrow(*buttons)

        # delta_to_str cannot take relative delta
        msg = await ctx.send(out_str, delete_after=300, components=[action_row])


    # =====================
    # events functions
    # =====================

    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):

        if ctx.custom_id.count('_') != 1:
            return

        command, rem_id = ctx.custom_id.split('_')

        try:
            rem_id = ObjectId(rem_id)
        except:
            return 

        
        if command == 'direct-delete':
            if Connector.delete_reminder(rem_id):
                await ctx.send('Deleted the reminder', hidden=True)
                Analytics.delete_reminder() 
            else:
                await ctx.send('Could not find a matching reminder for this component.\nThe reminder is already elapsed or was deleted', hidden=True)
        elif command == 'direct-interval':
            await lib.ReminderRepeater.spawn_interval_setup(self.client, ctx, rem_id)


    @commands.Cog.listener()
    async def on_ready(self):
        print('ReminderModule loaded')


    @tasks.loop(minutes=1)
    async def check_pending_reminders(self):
        now = datetime.utcnow()

        pending_rems = Connector.pop_elapsed_reminders(now.timestamp())
        
        for reminder in pending_rems:
            await self.print_reminder(reminder)
    

    @check_pending_reminders.before_loop
    async def check_pending_reminders_before(self):
        await self.client.wait_until_ready()

   
    @tasks.loop(minutes=15)
    async def check_reminder_cnt(self):
        now = datetime.utcnow()

        rems = Connector.get_reminder_cnt()
        Analytics.active_reminders(rems)
        

    @check_reminder_cnt.before_loop
    async def check_reminder_cnt_before(self):
        await self.client.wait_until_ready()

    # =====================
    # commands functions
    # =====================

    @cog_ext.cog_slash(name='remind', description='set a reminder for another user',
                        options=[
                            create_option(
                                name='user',
                                description='the user you want to remind',
                                required=True,
                                option_type=SlashCommandOptionType.USER
                            ),
                            create_option(
                                name='period',
                                description='the time after you\'re reminded',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            ),
                            create_option(
                                name='message',
                                description='the bot will remind you with this message',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            )
                        ])
    @commands.guild_only()
    async def add_remind_user(self, ctx, user, period, message):
        await self.process_reminder(ctx, ctx.author, user, period, message)
    
   
    @cog_ext.cog_slash(name='remindme', description='set a reminder after a certain time period',
                        options=[
                            create_option(
                                name='period',
                                description='the time after you\'re reminded',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            ),
                            create_option(
                                name='message',
                                description='the bot will remind you with this message',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            )
                        ])
    async def remindme(self, ctx, period, message):
        await self.process_reminder(ctx, ctx.author, ctx.author, period, message)


def setup(client):
    client.add_cog(ReminderModule(client))
