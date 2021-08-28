import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from bson import ObjectId

import copy
from pytz import common_timezones as pytz_common_timezones, country_timezones

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Reminder import Reminder, IntervalReminder
import lib.input_parser
import lib.ReminderRepeater

from lib.Analytics import Analytics, Types
from ReminderListing import ReminderListing


class ReminderModule(commands.Cog):

    REMIND_FORMAT_HELP = '```'\
                'examples:\n'\
                '\t/remindme 1y Hello future me\n'\
                '\t/remindme 2 h drink some water\n'\
                '\t/remindme 1w 2d hello there\n'\
                '\t/remindme 2021-09-02T12:25:00+02:00 iso is cool\n'\
                '\n'\
                '\t/remind @User 1 mon What\'s up\n'\
                '\t/remind @User 24 dec Merry Christmas\n'\
                '\t/remind @Role eoy Happy new year\n'\
                '\n'\
                '\t/remindme every friday at 20:15 do stuff\n'\
                '\t/remind @User every year at 1st july happy birthday\n'\
                '\n\n'\
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
                '\t• 2030\n'\
                '\t• every other week\n'\
                '\tNote: the parser uses day-first and year-least\n'\
                '\t      (01/02/03 -> 1st February 2003)\n'\
                '\n'\
                'the reminder can occur as much as 1 minute delayed\n'\
                'repeating reminders can occur as much as 5 minutes delayed```\n'\
                
    HELP_FOOTER = 'If you find a bug in the parser, please reach out to us.\n'\
                  'You can contact us on [Github](https://github.com/Mayerch1/RemindmeBot) or join the support server.'


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
        
        self.timezone_country = {}
        for countrycode in country_timezones:
            timezones = country_timezones[countrycode]
            for timezone in timezones:
                self.timezone_country[timezone] = countrycode

        print('starting reminder event loops')
        self.check_pending_reminders.start()
        self.check_pending_intervals.start()
        self.check_reminder_cnt.start()
        self.check_interval_cnt.start()
        self.clean_interval_orphans.start()

    def cog_unload(self):
        print('stopping reminder event loops')
        self.check_pending_reminders.cancel()
        self.check_pending_intervals.cancel()
        self.check_reminder_cnt.cancel()
        self.check_interval_cnt.cancel()
        self.clean_interval_orphans.cancel()

    async def print_reminder_dm(self, rem: Reminder, err_msg=None):
        # fallback to dm
        # target must be resolved, otherwise dm cannot be created

        try:
            target = await self.client.fetch_user(rem.target)
        except discord.errors.NotFound:
            print(f'cannot find user {rem.target} for reminder DM fallback')
            Analytics.reminder_not_delivered(rem, Types.DeliverFailureReason.USER_FETCH)
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
                Analytics.reminder_not_delivered(rem, Types.DeliverFailureReason.DM_SEND)


    async def print_reminder(self, rem: Reminder):
        # reminder is a DM reminder
        if not rem.g_id:
            await self.print_reminder_dm(rem)
            return

        guild = self.client.get_guild(rem.g_id)
        channel = guild.get_channel(rem.ch_id) if guild else None

        # no need to resolve author, target is sufficient
        if not channel:
            guild_name = guild.name if guild else 'Unresolved Guild'
            err = f'`You are receiving this dm, as the reminder was created in a thread or as the channel on \'{guild_name}\' is not existing anymore.`'
            await self.print_reminder_dm(rem, err)
            return

        eb = await rem.get_embed(self.client)

        # first fallback is string-only message
        # second fallback is dm to user

        perms = channel.permissions_for(guild.me)

        if perms.send_messages and perms.embed_links:
            try:
                # embed does not hold user mention
                await channel.send(rem.target_mention or f'<@{rem.target}>', embed=eb, 
                                   allowed_mentions=discord.AllowedMentions.all())
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


    async def process_reminder(self, ctx, author, target, period, message):

        if ctx.guild:
            instance_id = author.guild.id
            # try and get the last message, for providing a jump link
            try:
                last_msg = await ctx.channel.history(limit=1).flatten()
            except:
                last_msg = None
            last_msg = last_msg[0] if last_msg else None
        else:
            instance_id = author.id
            last_msg = None

        tz_str = Connector.get_timezone(instance_id)
        
        utcnow = datetime.utcnow()
        remind_at, info = lib.input_parser.parse(period, utcnow, tz_str)
        rrule = None
        
        if isinstance(remind_at, datetime):
            interval = (remind_at - utcnow)
            if remind_at is None or interval <= timedelta(hours=0):
                if info != '':
                    out_str = f'```Parsing hints:\n{info}```\n'
                else:
                    out_str = ''

                if interval == timedelta(hours=0):
                    # only append full help on invalid strings
                    # not on negative intervals
                    out_str += ReminderModule.REMIND_FORMAT_HELP
                out_str += ReminderModule.HELP_FOOTER
                
                embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
                await ctx.send(embed=embed, hidden=True)
                
                if interval == timedelta(hours=0):
                    Analytics.reminder_creation_failed(Types.CreationFailed.INVALID_F_STR)
                else:
                    Analytics.reminder_creation_failed(Types.CreationFailed.PAST_DATE)
                return  # error exit
        elif remind_at is None:
            if info != '':
                out_str = f'```Parsing hints:\n{info}```\n'
            else:
                out_str = ''
            out_str += ReminderModule.REMIND_FORMAT_HELP
            out_str += ReminderModule.HELP_FOOTER
            embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
            await ctx.send(embed=embed, hidden=True)
            Analytics.reminder_creation_failed(Types.CreationFailed.INVALID_F_STR)  
            return  
        elif isinstance(remind_at, str):
            rrule, info = lib.input_parser.rrule_normalize(remind_at, utcnow, instance_id)
            if not rrule:
                if info != '':
                    out_str = f'```Parsing hints:\n{info}```\n'
                else:
                    # only show general help, if normalizing doesn't give
                    # specific error
                    out_str += ReminderModule.REMIND_FORMAT_HELP

                out_str += ReminderModule.HELP_FOOTER
                embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
                await ctx.send(embed=embed, hidden=True)
                Analytics.reminder_creation_failed(Types.CreationFailed.INVALID_F_STR)  
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
        
        rem.created_at = utcnow
        rem.last_msg_id = last_msg.id if last_msg else None


        if isinstance(target, int):
            # use user-mention (no &) as fallback
            # as it's more likely to not resolve a user
            rem.target = target
            rem.target_name = f'<@{target}>'
            rem.target_mention = f'<@{target}>'
            print('failed to resolve mentionable')
        elif isinstance(target, discord.member.Member):
            rem.target = target.id
            rem.target_name = target.mention
            rem.target_mention = target.mention
        else:
            rem.target = target.id
            rem.target_name = target.name
            # everyone requires a special case
            # as it cannot be mentioned by using the id
            if ctx.guild and ctx.guild.default_role == target:
                rem.target_mention = target.name # @everyone
            else:
                rem.target_mention = target.mention

        if rrule:
            old_rem = rem
            old_rem.at = utcnow
            rem = IntervalReminder(old_rem._to_json())
            rem.first_at = old_rem.at
            rem.rrules.append(str(rrule))
            
            rem.at = rem.next_trigger(utcnow)

            rem_id = Connector.add_interval(rem)
            Analytics.reminder_created(rem, country_code=self.timezone_country.get(tz_str, 'UNK'), direct_interval=True)
        else:
            # the id is required in case the users wishes to abort
            rem_id = Connector.add_reminder(rem)
            Analytics.reminder_created(rem, country_code=self.timezone_country.get(tz_str, 'UNK'))


        # create the button to delete this reminder
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.primary,
                label='Edit Interval' if isinstance(rem, IntervalReminder) else 'Set Interval',
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
        
        if not ctx.channel:
            info = 'If this command was invoked in a thread, you will receive the reminder as a DM. Make sure you can receive DMs from me.'
            
        tiny_embed = rem.get_tiny_embed(info=info, rrule_override=rrule)
        msg = await ctx.send(embed=tiny_embed, delete_after=300, components=[action_row], 
                            allowed_mentions=discord.AllowedMentions.none())


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

        # make sure the user owns the reminder
        author_id = Connector.get_author_of_id(rem_id)
        if not author_id:
            await ctx.send('Could not find a matching reminder for this component.\nThe reminder is already elapsed or was deleted', hidden=True)
            return
        elif author_id != ctx.author.id:
            await ctx.send('You\'re not the author of this reminder', hidden=True)
            return
        
        # either edit the interval, or delete the reminder
        if command == 'direct-delete':
            if Connector.delete_reminder(rem_id):
                await ctx.send('Deleted the reminder', hidden=True)
                Analytics.reminder_deleted(Types.DeleteAction.DIRECT_BTN) 
            elif Connector.delete_interval(rem_id):
                await ctx.send('Deleted the reminder', hidden=True)
                Analytics.interval_deleted(Types.DeleteAction.DIRECT_BTN) 
            else:
                await ctx.send('Failed to delete reminder due to an unknown issue', hidden=True)
        elif command == 'direct-interval':
            await lib.ReminderRepeater.spawn_interval_setup(self.client, ctx, rem_id)


    @commands.Cog.listener()
    async def on_ready(self):
        print('ReminderModule loaded')


    @tasks.loop(hours=24)
    async def clean_interval_orphans(self):
        cnt = Connector.delete_orphaned_intervals()

        for _ in range(cnt):
            Analytics.reminder_deleted(Types.DeleteAction.ORPHAN)

        print(f'deleted {cnt} orphaned interval(s)')


    @tasks.loop(minutes=2)
    async def check_pending_intervals(self):
        now = datetime.utcnow()

        pending_intvls = Connector.get_pending_intervals(now.timestamp())

        for interval in pending_intvls:
            interval.at = interval.next_trigger(now)
            Connector.update_interval_at(interval)
            
        for interval in pending_intvls:
            await self.print_reminder(interval)
    

    @tasks.loop(minutes=1)
    async def check_pending_reminders(self):
        now = datetime.utcnow()

        pending_rems = Connector.pop_elapsed_reminders(now.timestamp())
        
        for reminder in pending_rems:
            await self.print_reminder(reminder)
    
   
    @tasks.loop(minutes=15)
    async def check_reminder_cnt(self):
        now = datetime.utcnow()

        rems = Connector.get_reminder_cnt()
        Analytics.reminder_cnt(rems)

    @tasks.loop(minutes=15)
    async def check_interval_cnt(self):
        intvls = Connector.get_interval_cnt()
        Analytics.interval_cnt(intvls)
    

    @clean_interval_orphans.before_loop
    async def clean_interval_orphans_before(self):
        await self.client.wait_until_ready()

    @check_pending_intervals.before_loop
    async def check_pending_intervals_before(self):
        await self.client.wait_until_ready()

    @check_pending_reminders.before_loop
    async def check_pending_reminders_before(self):
        await self.client.wait_until_ready()

    @check_reminder_cnt.before_loop
    async def check_reminder_cnt_before(self):
        await self.client.wait_until_ready()

    @check_interval_cnt.before_loop
    async def check_interval_cnt_before(self):
        await self.client.wait_until_ready()

    # =====================
    # commands functions
    # =====================

    @cog_ext.cog_slash(name='remind', description='set a reminder for another user',
                        options=[
                            create_option(
                                name='target',
                                description='the user or role you want to remind',
                                required=True,
                                option_type=SlashCommandOptionType.MENTIONABLE
                            ),
                            create_option(
                                name='time',
                                description='time/date when the reminder is triggered (or initial date for repeating reminders, see /help syntax)',
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
    async def add_remind_user(self, ctx, target, time, message):

        target_resolve = ctx.guild.get_member(int(target)) or ctx.guild.get_role(int(target))
        
        if not target_resolve:
            target_resolve = await ctx.guild.fetch_member(int(target))
            
        # if resolve failed, use plain id
        target_resolve = target_resolve or int(target) 

        await self.process_reminder(ctx, ctx.author, target_resolve, time, message)
    
   
    @cog_ext.cog_slash(name='remindme', description='set a reminder after a certain time period',
                        options=[
                            create_option(
                                name='time',
                                description='time/date when the reminder is triggered (or initial date for repeating reminders, see /help syntax)',
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
    async def remindme(self, ctx, time, message):
        await self.process_reminder(ctx, ctx.author, ctx.author, time, message)


def setup(client):
    client.add_cog(ReminderModule(client))
