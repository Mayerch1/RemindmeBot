import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from dateutil.relativedelta import *
import copy

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType

from datetime import datetime, timedelta

from lib.Connector import Connector
from lib.Reminder import Reminder


# WARNING: needs PyNaCl package installed
class ReminderModule(commands.Cog):

    REMIND_FORMAT_HELP = '```allowed intervals are\n'\
                '\t• y(ears)\n'\
                '\t• mo(nths)\n'\
                '\t• w(eeks)\n'\
                '\t• d(ays)\n'\
                '\t• h(ours)\n'\
                '\t• mi(ns)\n'\
                '\t• eoy - remind at end of year\n'\
                '\t• eom - remind at end of month\n'\
                '\t• eow - remind at end of week\n'\
                '\t• eod - remind at end of day\n'\
                '\n'\
                'the reminder can occur as much as 1 minutes delayed```'


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


    async def get_rem_embed(self, rem: Reminder, is_dm=False):

        if rem.target != rem.author:
            try:
                author = await self.client.fetch_user(rem.author)
                title = 'Reminds you'
            except discord.errors.NotFound:
                author = None
                title = f'Reminder'
        else:
            author = None
            title = f'Reminder'


        eb = discord.Embed(title=title, description=f'<@!{rem.target}>\n{rem.msg}', color=0xffcc00)

        if rem.created_at:
            eb.set_footer(text='created at {:s}'.format(rem.created_at.strftime('%Y-%m-%d %H:%M')))


        if author:
            eb.set_author(name=author.display_name, icon_url=author.avatar_url)

        elif rem.target != rem.author:
            # fallback if author couldn't be determined
            eb.add_field(name='delivered by', value=f'<@!{rem.author}>')


        if rem.g_id and rem.last_msg_id:
            url = f'https://discord.com/channels/{rem.g_id}/{rem.ch_id}/{rem.last_msg_id}'
            eb.add_field(name='\u200B', value=f'[jump to the chat]({url})')


        return eb


    def get_rem_string(self, rem: Reminder, is_dm=False):

        if rem.target == rem.author:
            out_str = f'Reminder: {rem.msg}'
        else:
            out_str = f'Reminder: {rem.msg} (delivered by <@{rem.author}>)'



        out_str += '\n||This reminder can be more beautiful with `Embed Links` permissions||'
        return out_str



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


        eb = await self.get_rem_embed(rem, is_dm=True)
        
        
        # first fallback is string-only message
        # second fallback is dm to user
        try:
            await dm.send(embed=eb)
            if err_msg:
                await dm.send(f'||{err_msg}||')
        except discord.errors.Forbidden:

            try:
                await dm.send(self.get_rem_string(rem, is_dm=True))
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


        eb = await self.get_rem_embed(rem)
        

        # first fallback is string-only message
        # second fallback is dm to user
        try:
            await channel.send(embed=eb)
        except discord.errors.Forbidden:

            try:
                await channel.send(self.get_rem_string(rem))
            except discord.errors.Forbidden:
                err = f'`You are receiving this dm, as I do not have permission to send messages into the channel \'{channel.name}\' on \'{guild.name}\'.`'
                await self.print_reminder_dm(rem, err)



        




    async def process_reminder(self, ctx, author, target, period, message):


        if ctx.guild:
            tz_str = Connector.get_timezone(author.guild.id)

            # try and get the last message, for providing a jump link
            last_msg = await ctx.channel.history(limit=1).flatten()
            last_msg = last_msg[0] if last_msg else None
        else:
            tz_str = 'UTC'
            last_msg = None

        
        err = False

        # try splitting first arg in int+string
        duration_arg = re.search(r'^\d+', period)
        interval_arg = re.search(r'[^0-9 ].*', period)

        if not interval_arg:
            await ctx.send(ReminderModule.REMIND_FORMAT_HELP)
            return

        # arg format was: 1y my text
        elif duration_arg:
            duration = ReminderModule.to_int(duration_arg.group())
            timearg = interval_arg.group()

        # arg format was: eoy my text
        else:
            timearg = interval_arg.group()

            
        
        now = datetime.utcnow()
        now_local = datetime.utcnow().replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str))

        if timearg == 'eoy':
            tmp = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            eoy = tmp + relativedelta(years=1, days=-1)
            intvl = eoy - now_local

        elif timearg == 'eom':
            tmp = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            eom = tmp + relativedelta(months=1, hours=-12)
            intvl = eom - now_local


        elif timearg == 'eow':
            w_day = now_local.weekday()
            week_start = now_local - timedelta(days=w_day)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

            eow = week_start + relativedelta(weeks=1, hours=-1)
            intvl = eow - now_local


        elif timearg == 'eod':
            tmp = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            eod = tmp + relativedelta(days=1, minutes=-15)
            intvl = eod - now_local
            
        elif timearg.startswith('y'):
            intvl = relativedelta(years=duration)

        elif timearg.startswith('mo'):
            intvl = relativedelta(months=duration)
            
        elif timearg.startswith('w'):
            intvl = relativedelta(weeks=duration)
            
        elif timearg.startswith('d'):
            intvl = timedelta(days=duration)
            
        elif timearg.startswith('h'):
            intvl = timedelta(hours=duration)

        elif timearg.startswith('mi'):
            intvl = timedelta(minutes=duration)

        else:
            err = True


        if err:
            if timearg == 'm':
                # specific help for month/minute completion
                await ctx.send('Unambiguous reference to minutes/months. Please write out at least `mi` for minutes or `mo` for months', hidden=True)
            else:
                await ctx.send(ReminderModule.REMIND_FORMAT_HELP, hidden=True)
            return

        # reminder is in utc domain
        remind_at = now + intvl

        rem = Reminder()

        if ctx.guild:
            rem.g_id = ctx.guild.id
            rem.ch_id = ctx.channel.id
        else:
            # command was called in DM
            rem.g_id = None
            rem.ch_id = None

        rem.msg = message
        rem.at = remind_at
        rem.author = author.id
        rem.target = target.id
        rem.created_at = now
        rem.last_msg_id = last_msg.id if last_msg else None

        Connector.add_reminder(rem)
        


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


        if target == author:
            out_str = f'Reminding you in {delta_to_str(remind_at-now)}'
        else:
            out_str = f'Reminding {target.name} in {delta_to_str(remind_at-now)}'

        if (remind_at-now) < timedelta(minutes=5):
            out_str += '\nBe aware that the reminder can be as much as 1 minute delayed'


        # delta_to_str cannot take relative delta
        await ctx.send(out_str, delete_after=120)



    # =====================
    # events functions
    # =====================
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
    async def add_remind_user(self, ctx, target, period, message):
        
        await self.process_reminder(ctx, ctx.author, target, period, message)
    
   


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
    async def add_remind_author(self, ctx, period, message):
        
        await self.process_reminder(ctx, ctx.author, ctx.author, period, message)
        
       



def setup(client):
    client.add_cog(ReminderModule(client))