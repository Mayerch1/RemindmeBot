import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from bson import ObjectId

import copy
from datetime import datetime
from dateutil import tz
from pytz import common_timezones as pytz_common_timezones, country_timezones

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Analytics import Analytics, Types


class SettingsModule(commands.Cog):
    
    def __init__(self, client):
        self.client = client
        
    
        
    ################
    # Helper methods
    ################
    
    def _get_tz_info_eb(self, name):
        
        zone = tz.gettz(name)

        offset = datetime.now(zone).strftime('%z')
        local_time = datetime.now(zone).strftime('%H:%M')

        info_str = ''
        if re.match(r'^UTC\+\d+$', name):
            info_str += '\n• Consider using your local timezone (instead of `UTC+X`), in order to automatically adjust to daylight-saving*'
        elif name.lower() == 'mst':
            info_str += '\n• Consider using `MST7MDT` to respect daylight saving during winter'
        elif name.lower() == 'est':
            info_str += '\n• Consider using `EST5EDT` to respect daylight saving during winter'
        elif name not in pytz_common_timezones:
            info_str += f'\n• `{name}` seems to be a deprecated timezone and could be discontinued in future versions.\n'\
                        f'• Try and use a geo-referenced timezone that _observes_ `{name}` instead (e.g. `Europe/Berlin`)'

        if not info_str:
            # no warnings means green embed
            col = 0x69eb67
        else:
            # some non-critical warnings will show slightly yellow embed
            col = 0xcceb67

        # put new timezone into embed title
        # but make sure the title is not exceeding 256 chars
        eb = discord.Embed(title=f'Current Timezone {name[:243]}',
                        color=col,
                        description=f'The timezone is set to `{name}` (`UTC{offset}`)\n'\
                                    f'This corresponds to a local time of `{local_time}`\n'\
                                    f'Use `/settings timezone` to edit this value')

        return eb
    
    
    def get_action_rows(self, instance_id):
        
        tz = Connector.get_timezone(instance_id)
        rem_type = Connector.get_reminder_type(instance_id)
        auto_delete = Connector.get_auto_delete(instance_id)
        
        action_rows = []
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label='Server Timezone',
                custom_id='settings_timezone_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.gray,
                label=tz,
                custom_id=f'settings_timezone_show_{instance_id}'
                
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Preferred Reminder Style',
                custom_id='settings_type_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (rem_type==Connector.ReminderType.HYBRID) else ButtonStyle.gray,
                label=f'Hybrid Reminders',
                disabled=(rem_type==Connector.ReminderType.HYBRID),
                custom_id=f'settings_type_hybrid_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (rem_type==Connector.ReminderType.EMBED_ONLY) else ButtonStyle.gray,
                label=f'Embed-Only Reminders',
                disabled=(rem_type==Connector.ReminderType.EMBED_ONLY),
                custom_id=f'settings_type_embed_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (rem_type==Connector.ReminderType.TEXT_ONLY) else ButtonStyle.gray,
                label=f'Text-Only Reminders',
                disabled=(rem_type==Connector.ReminderType.TEXT_ONLY),
                custom_id=f'settings_type_text_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Delete Creation Dialog',
                custom_id='settings_autodel_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (auto_delete==Connector.AutoDelete.TIMEOUT) else ButtonStyle.gray,
                label=f'Delete after Timeout',
                disabled=(auto_delete==Connector.AutoDelete.TIMEOUT),
                custom_id=f'settings_autodel_timeout_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (auto_delete==Connector.AutoDelete.NEVER) else ButtonStyle.gray,
                label=f'Never Delete',
                disabled=(auto_delete==Connector.AutoDelete.NEVER),
                custom_id=f'settings_autodel_never_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (auto_delete==Connector.AutoDelete.HIDE) else ButtonStyle.gray,
                label=f'Only Show to author',
                disabled=(auto_delete==Connector.AutoDelete.HIDE),
                custom_id=f'settings_autodel_hide_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        return action_rows

    
    ################
    # idk whats that
    ################

    async def show_settings_page(self, ctx: SlashContext):
        
        # if no guild is present
        # assume dm context
        instance_id = ctx.guild.id if ctx.guild else ctx.author.id
        
        eb = discord.Embed(title='Remindme Settings',
                           description='Server Managers can edit these settings by pressing the '\
                                        'corresponding buttons below.\n'\
                                        'The grayed-out buttons are the current selected options.')
        
        a_rows = self.get_action_rows(instance_id)
        await ctx.send(embed=eb, components=a_rows, hidden=True)


    async def set_reminder_type(self, ctx, args):
        
        if not args or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        
        # perform permission checks for modifying settings
        # if author is User means that the command was invoked in DMs
        # there's no need for permission in DMs
        if isinstance(ctx.author, discord.Member):
            perms =  ctx.author.guild_permissions
            
            if not perms.administrator and not perms.manage_guild:
                await ctx.send('You need to have the `manage_server` permission to modify these settings', hidden=True)
                return
        
        new_type = args[0]
        instance_id = int(args[1])

        if new_type == 'hybrid':
            new_enum = Connector.ReminderType.HYBRID
        elif new_type == 'text':
            new_enum = Connector.ReminderType.TEXT_ONLY
        elif new_type == 'embed':
            new_enum = Connector.ReminderType.EMBED_ONLY
        else:
            return
        
        Connector.set_reminder_type(instance_id, new_enum)
        Analytics.set_reminder_type(new_enum)
        
        a_rows = self.get_action_rows(instance_id=instance_id)
        await ctx.edit_origin(components=a_rows)
    
    
    async def set_autodel(self, ctx, args):
        
        if not args or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        # perform permission checks for modifying settings
        # if author is User means that the command was invoked in DMs
        # there's no need for permission in DMs
        if isinstance(ctx.author, discord.Member):
            perms =  ctx.author.guild_permissions
            
            if not perms.administrator and not perms.manage_guild:
                await ctx.send('You need to have the `manage_server` permission to modify these settings', hidden=True)
                return
        
        new_type = args[0]
        instance_id = int(args[1])

        if new_type == 'timeout':
            new_enum = Connector.AutoDelete.TIMEOUT
        elif new_type == 'never':
            new_enum = Connector.AutoDelete.NEVER
        elif new_type == 'hide':
            new_enum = Connector.AutoDelete.HIDE
        else:
            return
        
        Connector.set_auto_delete(instance_id, new_enum)
        Analytics.set_auto_delete(new_enum)
        
        a_rows = self.get_action_rows(instance_id=instance_id)
        await ctx.edit_origin(components=a_rows)
    
    
    async def show_timezone_hint(self, ctx, args):
        
        if not args or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
    
        elif args[0] == 'show':
            instance_id = int(args[1])
            tz = Connector.get_timezone(instance_id)
            eb = self._get_tz_info_eb(tz)
            await ctx.send(embed=eb, hidden=True)


    ################
    # Event methods
    ################

    @commands.Cog.listener()
    async def on_ready(self):
        print('SettingsModule loaded')
        
        
    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):
        
        args = ctx.custom_id.split('_')
        
        # args 0 must exists
        if args[0] != 'settings' or len(args) < 2:
            return
        
        if args[1] == 'type':
            await self.set_reminder_type(ctx, args[2:])
        elif args[1] == 'timezone':
            await self.show_timezone_hint(ctx, args[2:])
        elif args[1] == 'autodel':
            await self.set_autodel(ctx, args[2:])

    ##################
    # Commands methods
    ##################

    @cog_ext.cog_subcommand(base='settings', name='menu', description='Get an overview over all settings') 
    async def settings_menu_cmd(self, ctx):
        await self.show_settings_page(ctx)




def setup(client):
    client.add_cog(SettingsModule(client))