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

import net.threads as Thread


class ReminderModule(commands.Cog):


    # =====================
    # internal functions
    # =====================


    def __init__(self, client):
        self.client = client

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
        
        
    async def warn_author_dm(self, rem: Reminder, reason, channel=None, err_msg=None):
        
        if rem.author == rem.target:
            # nothing be done here
            # dm already failed before
            Analytics.reminder_not_delivered(rem, reason)
            return
        
        # try to notify the author of the reminder
        try:
            author = await self.client.fetch_user(rem.author)
        except discord.errors.NotFound:
            print(f'cannot find user {rem.author} for author warning')
            Analytics.reminder_not_delivered(rem, Types.DeliverFailureReason.AUTHOR_WARN_FAILED)
            return
        
        guild = self.client.get_guild(rem.g_id) if rem.g_id else None
        dm =  await author.create_dm()
        eb = rem.get_info_embed()
        
        help_text = 'Couldn\'t send the reminder into the requested channel\n\n'\
                   f'• Make sure I have permission to send messages into the channel `{channel.name}` on `{guild.name}`\n'\
                    '• or make sure the receiver allows to receive DMs from me\n'\
                    '• or edit the Reminder to be send into an existing channel'\
                    if channel and guild else \
                    'The reminder was created within a thread, or the initial channel is not existing anymore\n\n'\
                    '• Make sure the receiver allows to receive DMs (if the receiver is a single User)\n'\
                    '• or edit the Reminder to be send into an existing channel'
        
        eb_warn = discord.Embed(title='Failed to deliver Reminder',
                                description=f'{help_text}',
                                color=0xff0000)

        try:
            await dm.send(embed=eb_warn)
            await dm.send(embed=eb)
        except discord.errors.Forbidden:
            # dm has no embed permissions, embeds must always succeed
            print(f'failed to send author warning')
            Analytics.reminder_not_delivered(rem, Types.DeliverFailureReason.AUTHOR_WARN_FAILED)
            return


    async def print_reminder_dm(self, rem: Reminder, channel=None, err_msg=None):
        # fallback to dm
        # target must be resolved, otherwise dm cannot be created

        try:
            target = await self.client.fetch_user(rem.target)
        except discord.errors.NotFound:
            print(f'cannot find user {rem.target} for reminder DM')
            await self.warn_author_dm(rem, Types.DeliverFailureReason.USER_FETCH, channel=channel, err_msg=err_msg)
            return

        # dm if channel not existing anymor
        dm =  await target.create_dm()
        
        
        # respect user preferences
        rem_type = Connector.get_reminder_type(rem.target)
        tz_str = Connector.get_timezone(rem.target)
        
        if rem_type == Connector.ReminderType.TEXT_ONLY:
            # text is identical to missing permission fallback
            # but the spoiler asking for more permissions is missing
            eb = None
            text = await rem.get_string(client=self.client, is_dm=True)
        elif rem_type == Connector.ReminderType.EMBED_ONLY:
            eb = await rem.get_embed(self.client, is_dm=True, tz_str=tz_str)
            text = ''
        else:
            eb = await rem.get_embed(self.client, is_dm=True, tz_str=tz_str)
            text = rem.get_embed_text(is_dm=True)

        
        # first fallback is string-only message
        # second fallback is dm to user
        # DM never requires user mention (DM itself is a ping)
        try:
            await dm.send(text, embed=eb)
            if err_msg:
                await dm.send(f'||{err_msg}||')
        except discord.errors.Forbidden:
            # embeds can't be forbidden in DMs
            print(f'failed to send reminder as DM')
            await self.warn_author_dm(rem, Types.DeliverFailureReason.DM_SEND, channel=channel, err_msg=err_msg)
            return


    async def print_reminder(self, rem: Reminder):

        async def send_message(guild, channel, text, embed):
            perms = channel.permissions_for(guild.me)
            if perms.send_messages and perms.embed_links:
                try:
                    await channel.send(text, embed=embed, 
                                    allowed_mentions=discord.AllowedMentions.all())
                    return True
                except discord.errors.Forbidden:
                    pass

            elif perms.send_messages:
                try:
                    # get the reminder string
                    # ignoring the user preferences
                    fallback = await rem.get_string(client=self.client)
                    fallback += '\n||This reminder can be more beautiful with `Embed Links` permissions||'
                    await channel.send(fallback)
                    return True
                except discord.errors.Forbidden:
                    pass
            
            return False

        # reminder is a DM reminder
        if not rem.g_id:
            await self.print_reminder_dm(rem)
            return

        guild = self.client.get_guild(rem.g_id)
        tz_str = Connector.get_timezone(rem.g_id)
        channel = guild.get_channel(rem.ch_id) if guild else None
        is_thread = Thread.exists(rem.ch_id) if guild else False

        # no need to resolve author, target is sufficient
        if not channel and not is_thread:
            guild_name = guild.name if guild else 'Unresolved Guild'
            err = f'`You are receiving this dm, as the desired channel on \'{guild_name}\' is not existing anymore.`'
            await self.print_reminder_dm(rem, channel=None, err_msg=err)
            return

        # respect guild preferences
        rem_type = Connector.get_reminder_type(guild.id)
        
        if rem_type == Connector.ReminderType.TEXT_ONLY:
            # text is identical to missing permission fallback
            # but the spoiler asking for more permissions is missing
            eb = None
            text = await rem.get_string(client=self.client)
        elif rem_type == Connector.ReminderType.EMBED_ONLY:
            eb = await rem.get_embed(self.client, tz_str=tz_str)
            text = rem.target_mention or f'<@{rem.target}>'
        else:
            eb = await rem.get_embed(self.client, tz_str=tz_str)
            text = rem.get_embed_text()

        # override reminder text

        if channel:
            success = await send_message(guild, channel, text, eb)
            err = f'`You are receiving this dm, as I do not have permission to send messages into the channel \'{channel.name}\' on \'{guild.name}\'.`'
        elif is_thread:
            dearchived = Thread.dearchive(rem.ch_id)
            if dearchived:
                success = Thread.send(rem.ch_id, text, eb.to_dict())
                err = f'`You are receiving this dm, as I do not have permission to send messages into the thread on \'{guild.name}\'.`'
            else:
                success = False
                err = f'You are receiving this dm, as I couldn\'t de-archive the thread this reminder was scheduled for.'
        else:
            # no else case logically possible
            err = 'An unknown error prevented the reminder from being send into the apropriate channel'

        if not success:
            await self.print_reminder_dm(rem, channel=channel, err_msg=err)

    # =====================
    # events functions
    # =====================



    @commands.Cog.listener()
    async def on_ready(self):
        print('ReminderModule loaded')


    @tasks.loop(hours=24)
    async def clean_interval_orphans(self):
        cnt = Connector.delete_orphaned_intervals()

        Analytics.reminder_deleted(Types.DeleteAction.ORPHAN, count=cnt)
        print(f'deleted {cnt} orphaned interval(s)')


    @tasks.loop(minutes=2)
    async def check_pending_intervals(self):
        now = datetime.utcnow()
        
        pending_intvls = Connector.get_pending_intervals(now.timestamp())

        for interval in pending_intvls:
            # must be evaluated before new at is assigned
            Analytics.reminder_delay(interval, now=now, allowed_delay=2*60)
            
            interval.at = interval.next_trigger(now)
            Connector.update_interval_at(interval)
            
        for interval in pending_intvls:
            try:
                await self.print_reminder(interval)
            except Exception as e:
                print(f'ERR - interval not delivered, skipping')
                print(e)
                pass

        self.last_loop = datetime.utcnow()
    

    @tasks.loop(minutes=1)
    async def check_pending_reminders(self):
        now = datetime.utcnow()

        pending_rems = Connector.pop_elapsed_reminders(now.timestamp())
        
        for reminder in pending_rems:
            try:
                await self.print_reminder(reminder)
            except Exception as e:
                print(f'ERR - reminder not delivered, skipping')
                print(e)
            Analytics.reminder_delay(reminder, now=now, allowed_delay=1*60)
    
   
    @tasks.loop(minutes=15)
    async def check_reminder_cnt(self):
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

def setup(client):
    client.add_cog(ReminderModule(client))
