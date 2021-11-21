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
from lib.CommunitySettings import CommunitySettings, CommunityAction
import lib.input_parser
import lib.ReminderRepeater
import util.interaction

from lib.Analytics import Analytics, Types
from ReminderListing import ReminderListing

import net.threads as Thread


class ReminderCreation(commands.Cog):

    REMIND_FORMAT_HELP = \
                'basic example:\n'\
                '> /remindme `time: 2d` `message: Hello World`\n'\
                '\n'\
                'remind other users and roles\n'\
                '> /remind `target: @Role` `time: 24 dec`  `message: Merry Christmas`\n'\
                '\n'\
                'create repeating reminders\n'\
                '> /remindme `time: every friday at 20:15` `message: do stuff`\n'\
                '\n'\
                'try different formats\n'\
                '```'\
                '• 5 jul, 5th july, july 5\n'\
                '• 23 aug at 3pm, 23 aug at 15\n'\
                '• every other week\n'\
                '\n'\
                '```'\
                '\n'\
                'Call `/help page: syntax` for more detailed information.\n'
                
    HELP_FOOTER = 'If you find a bug in the parser, please reach out to us.\n'\
                  'You can contact us on Github or join the support server.'


    @staticmethod
    def to_int(num_str: str, base: int=10):
        
        try:
            conv_int = int(num_str, base)
        except ValueError:
            conv_int = None
        finally:
            return conv_int

        
    class UnsupportedChannelType(Exception):
        pass

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


    def sanitize_channel(self, ctx, channel):
        """chooses the correct channel to deliver the reminder
           
           will raise on unsupported types
           will select command channel if channel is not given

        Args:
            ctx ([type]): [description]
            channel (discord.TextChannel): target channel, None for command channel/thread

        Raises:
            ReminderCreation.UnsupportedChannelType: on unsupported channel type, like VoiceChannel

        Returns:
            discord.TextChannel or int: selected channel, channel_id for threads, None for DM sessions
        """

        if channel and isinstance(channel, discord.TextChannel):
            return channel
        elif channel:
            raise ReminderCreation.UnsupportedChannelType(f'Only channels of type `Text` or `Thread` are supported')

        # handle an implicitly called channel type
        if ctx.guild and ctx.channel:
            # respond to channel of call
            return ctx.channel
        elif ctx.guild:
            return ctx.channel_id
        else:
            # this is a dm session
            return None
 

    async def process_reminder(self, ctx, author, target, period, message, channel):

        # parse the channel
        try:
            channel = self.sanitize_channel(ctx, channel)
        except ReminderCreation.UnsupportedChannelType as e:
            eb = discord.Embed(title='Unsupported Channel-Type', description=str(e))
            eb.color = 0xff0000
            await ctx.send(embed=eb)
            return

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
        auto_del_action = Connector.get_auto_delete(instance_id)
        is_legacy = Connector.is_legacy_interval(instance_id)

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
                    out_str += ReminderCreation.REMIND_FORMAT_HELP
                elif interval < timedelta(hours=0):
                    out_str += 'Make sure your server is using the correct timezone `/settings timezone`'

                embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
                embed.set_footer(text=ReminderCreation.HELP_FOOTER)
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
            out_str += ReminderCreation.REMIND_FORMAT_HELP

            embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
            embed.set_footer(text=ReminderCreation.HELP_FOOTER)
            await ctx.send(embed=embed, hidden=True)
            Analytics.reminder_creation_failed(Types.CreationFailed.INVALID_F_STR)  
            return  

        elif isinstance(remind_at, str):

            if is_legacy:
                dtstart = utcnow
            else:
                dtstart = utcnow.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str)).replace(tzinfo=None)

            rrule, info = lib.input_parser.rrule_normalize(remind_at, dtstart=dtstart, instance_id=instance_id)
            if not rrule:
                if info != '':
                    out_str = f'```Parsing hints:\n{info}```\n'
                else:
                    # only show general help, if normalizing doesn't give
                    # specific error
                    out_str = ReminderCreation.REMIND_FORMAT_HELP

                embed = discord.Embed(title='Failed to create the reminder', color=0xff0000, description=out_str)
                embed.set_footer(text=ReminderCreation.HELP_FOOTER)
                await ctx.send(embed=embed, hidden=True)
                Analytics.reminder_creation_failed(Types.CreationFailed.INVALID_F_STR)  
                return
            
            elif not await util.interaction.check_user_permission(ctx, required_perms=CommunityAction(repeating=True)):
                # make sure the user is allowed to create repeating reminders
                return

        if auto_del_action == Connector.AutoDelete.HIDE:
            defer_hidden=True
        else:
            defer_hidden=False
        await ctx.defer(hidden=defer_hidden) # allow more headroom for response latency, before command fails
        rem = Reminder()



        info = '' if not info else info
        if channel is None:
            # command was called in DM
            rem.g_id = None
            rem.ch_id = None
            rem.ch_name = 'DM'
        elif isinstance(channel, int):
            # likely a thread, or unresolved channel
            rem.g_id = ctx.guild.id
            rem.ch_id = channel
            rem.ch_name = Thread.name(channel) # thread name

            if not Thread.exists(channel):
                info += '\n• I might not have access to this thread/channel. Make sure to adjust my permissions'
        else:
            # normal text channel
            rem.g_id = ctx.guild.id
            rem.ch_id = channel.id
            rem.ch_name = channel.name[0:25] # only keep first 25 letters

            if rem.ch_id != ctx.channel_id:
                info += f'\n• This reminder will be delivered to `{channel.name}`.\nMake sure this bot has permission to send messages into that channel'


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
            old_rem.at = dtstart
            rem = IntervalReminder(old_rem._to_json())
            rem.first_at = old_rem.at
            rem.rrules.append(str(rrule))

            rem.at = rem.next_trigger(utcnow, tz_str=tz_str)
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

        if auto_del_action == Connector.AutoDelete.TIMEOUT:
            delete_after = 300
            hidden=False
        elif auto_del_action == Connector.AutoDelete.NEVER:
            delete_after = None
            hidden=False
        else:
            delete_after = None
            hidden=True

        tiny_embed = rem.get_tiny_embed(info=info, rrule_override=rrule)
        msg = await ctx.send(embed=tiny_embed, delete_after=delete_after, components=[action_row], 
                            allowed_mentions=discord.AllowedMentions.none(), hidden=hidden)


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
            try:
                await ctx.send('Could not find a matching reminder for this component.\nThe reminder is already elapsed or was deleted', hidden=True)
            except discord.NotFound:
                pass
            return
        elif author_id != ctx.author.id:
            try:
                await ctx.send('You\'re not the author of this reminder', hidden=True)
            except discord.NotFound:
                pass
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
        print('ReminderCreation loaded')


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
                            ),
                            create_option(
                                name='channel',
                                description='A channel other than the current one',
                                required=False,
                                option_type=SlashCommandOptionType.CHANNEL
                            )
                        ])
    @commands.guild_only()
    async def add_remind_user(self, ctx, target, time, message, channel=None):
        
        target_resolve = ctx.guild.get_member(int(target)) or ctx.guild.get_role(int(target))
        
        if not target_resolve:
            # delays execution significantly, only if not already cached
            target_resolve = await ctx.guild.fetch_member(int(target))

        # if resolve failed, use plain id
        target_resolve = target_resolve or int(target) 

        # determining if the mention is @everyone depends
        # on how the role was resolved (and if it even is a role)
        if not ctx.guild:
            is_everyone = False
        elif isinstance(target_resolve, int):
            is_everyone = (ctx.guild.id == target_resolve)
        else:
            is_everyone = (ctx.guild.default_role == target_resolve)

        # only allow execution if all permissions are present        
        action = CommunityAction(foreign=True, everyone=is_everyone)
        if await util.interaction.check_user_permission(ctx, required_perms=action):
            await self.process_reminder(ctx, ctx.author, target_resolve, time, message, channel=channel)
    
   
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
                            ),
                            create_option(
                                name='channel',
                                description='A channel other than the current one',
                                required=False,
                                option_type=SlashCommandOptionType.CHANNEL
                            )
                        ])
    async def remindme(self, ctx, time, message, channel=None):

        if await util.interaction.check_user_permission(ctx):
            await self.process_reminder(ctx, ctx.author, ctx.author, time, message, channel=channel)


def setup(client):
    client.add_cog(ReminderCreation(client))
