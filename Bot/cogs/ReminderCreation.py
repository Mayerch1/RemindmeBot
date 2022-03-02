import asyncio
import re
import logging
from typing import Union

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from bson import ObjectId

import copy
from pytz import common_timezones as pytz_common_timezones, country_timezones

import discord
from discord.ext import commands, tasks

from util.consts import Consts
from lib.Connector import Connector
from lib.Reminder import Reminder, IntervalReminder
from lib.CommunitySettings import CommunitySettings, CommunityAction
import lib.input_parser
import lib.permissions
import lib.ReminderRepeater
import util.interaction
import util.reminderInteraction

from lib.Analytics import Analytics, Types


log = logging.getLogger('Remindme.Creation')


class NewReminderView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm: util.reminderInteraction.STM, info_str: str, rrule_override, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reminder = reminder
        self.stm = stm
        self.info_str = info_str
        self.rrule_override = rrule_override

        if isinstance(self.reminder, IntervalReminder):
            self.edit_interval.label='Edit Interval'

    def get_embed(self) -> discord.Embed:
        return self.reminder.get_tiny_embed(info=self.info_str, rrule_override=self.rrule_override)


    @discord.ui.button(label='Set Interval', emoji='🔁', style=discord.ButtonStyle.primary)
    async def edit_interval(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        view = util.reminderInteraction.ReminderIntervalAddView(self.reminder, self.stm, self.message)
        await interaction.response.edit_message(embed=view.get_embed(), view=view)
        await view.wait()

        self.message = view.message # could've migrated
        self.reminder = view.reminder # could be an interval with different id now

        # re-send this button menu
        if isinstance(self.message, discord.WebhookMessage):
            func = self.message.edit
        else:
            func = self.message.edit_original_message

        await func(embed=self.get_embed(), view=self)


    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.danger)
    async def del_reminder(self, button: discord.ui.Button, interaction: discord.Interaction):
        eb_title = None
        if Connector.delete_reminder(self.reminder._id):
            eb_title = 'Deleted the reminder'
            color = Consts.col_warn
            Analytics.reminder_deleted(Types.DeleteAction.DIRECT_BTN) 
        elif Connector.delete_interval(self.reminder._id):
            eb_title = 'Deleted the reminder'
            color = Consts.col_warn
            Analytics.interval_deleted(Types.DeleteAction.DIRECT_BTN) 
        else:
            eb_title = 'Failed to delete reminder due to an unknown issue'
            color = Consts.col_crit
            log.error(f'Couldn\'t direct-delete a reminder of type {type(self.reminder)}. Both delete queries didn\'t suceed.')


        eb = discord.Embed(title=eb_title, color=color)
        self.disable_all()
        self.del_reminder.style = discord.ButtonStyle.danger # keep this btn red
        await interaction.response.edit_message(embed=eb, view=self)
        self.stop()



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


    async def process_reminder(self, ctx: discord.ApplicationContext, author: Union[discord.User, discord.Member], target, period, message, channel):

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
            
            elif not lib.permissions.check_user_permission(ctx.guild.id, ctx.author.roles, required_perms=CommunityAction(repeating=True)):
                # make sure the user is allowed to create repeating reminders
                return

        if auto_del_action == Connector.AutoDelete.HIDE:
            defer_hidden=True
        else:
            defer_hidden=False
        await ctx.defer(ephemeral=defer_hidden) # allow more headroom for response latency, before command fails
        rem = Reminder()


        info = '' if not info else info
        if channel is None:
            # command was called in DM
            rem.g_id = None
            rem.ch_id = None
            rem.ch_name = 'DM'
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
            rem._id = Connector.add_interval(rem)
            Analytics.reminder_created(rem, country_code=self.timezone_country.get(tz_str, 'UNK'), direct_interval=True)
        else:
            # the id is required in case the users wishes to abort
            rem._id = Connector.add_reminder(rem)
            Analytics.reminder_created(rem, country_code=self.timezone_country.get(tz_str, 'UNK'))


        if auto_del_action == Connector.AutoDelete.TIMEOUT:
            delete_after = 300
            hidden=False
        elif auto_del_action == Connector.AutoDelete.NEVER:
            delete_after = None
            hidden=False
        else:
            delete_after = None
            hidden=True


        stm = util.reminderInteraction.STM(
            ctx,
            Connector.Scope(is_private=False, guild_id=ctx.guild.id, user_id=ctx.author.id)
        )
        stm.tz_str = tz_str

        view = NewReminderView(rem, stm=stm, info_str=info, rrule_override=rrule, timeout=delete_after)
        tiny_embed = view.get_embed() 

        msg = await ctx.respond(embed=tiny_embed, delete_after=delete_after, view=view, 
                            allowed_mentions=discord.AllowedMentions.none(), ephemeral=hidden)
        view.message = msg


    # =====================
    # events functions
    # =====================

    @discord.Cog.listener()
    async def on_ready(self):
        log.info('loaded')


    # =====================
    # commands functions
    # =====================

    @commands.slash_command(name='remind', description='set a reminder after a certain time period', guild_ids=[140150091607441408])
    async def remind_user(self, ctx:discord.ApplicationContext,
                        target:discord.Option(discord.Role, 'the user or role you want to remind', required=True),
                        time:discord.Option(str, 'time/date when the reminder is triggered (see syntax page on /help)', required=True),
                        message:discord.Option(str, 'the bot will remind you with this message', required=True), 
                        channel:discord.Option(discord.TextChannel, 'Show the reminder in a channel other than the current one', required=False)=None):

        if not target:
            # delays execution significantly, only if not already cached
            target_resolve = await ctx.guild.fetch_member(int(target))

        # determining if the mention is @everyone depends
        # on how the role was resolved (and if it even is a role)
        if not ctx.guild:
            is_everyone = False
        elif isinstance(target, int):
            is_everyone = (ctx.guild.id == target)
        else:
            is_everyone = (ctx.guild.default_role == target)

        # only allow execution if all permissions are present        
        action = CommunityAction(foreign=True, everyone=is_everyone)
        err_eb = lib.permissions.get_missing_permissions_embed(ctx.guild.id, ctx.author.roles, required_perms=action)
        if err_eb:
            await ctx.respond(embed=err_eb)
            return


        await self.process_reminder(ctx, ctx.author, target, time, message, channel=channel)
    

    @commands.slash_command(name='remindme', description='set a reminder after a certain time period', guild_ids=[140150091607441408])
    async def remindme(self, ctx:discord.ApplicationContext,
                        time:discord.Option(str, 'time/date when the reminder is triggered (see syntax page on /help)', required=True),
                        message:discord.Option(str, 'the bot will remind you with this message', required=True), 
                        channel:discord.Option(discord.TextChannel, 'Show the reminder in a channel other than the current one', required=False)=None):

        if ctx.guild:
            # call will fail if community mode is enabled
            err_eb = lib.permissions.get_missing_permissions_embed(ctx.guild.id, ctx.author.roles)
            if err_eb:
                await ctx.respond(embed=err_eb)
                return
            channel = channel or ctx.channel # overwrite if not specified

        await self.process_reminder(ctx, ctx.author, ctx.author, time, message, channel=channel)


def setup(client):
    client.add_cog(ReminderCreation(client))
