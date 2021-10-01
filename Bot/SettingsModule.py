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
from lib.CommunitySettings import CommunitySettings
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


    def get_navigation_menu(self, instance_id, page=1):
        
        options = [
            manage_components.create_select_option(
                label='Basic Page',
                description='Holds most important settings',
                value='1',
                emoji='🌐',
                default=(page==1)
            ),
            manage_components.create_select_option(
                label='Community Page',
                description='Show community related settings',
                value='2',
                emoji='👪',
                default=(page==2)
            )
        ]
        help_selection = (
            manage_components.create_select(
                custom_id=f'settings_navigation_{instance_id}',
                placeholder='Please select a page',
                min_values=1,
                max_values=1,
                options=options
            )
        )

        row = manage_components.create_actionrow(help_selection)
        return row
    
    
    def get_action_rows_page1(self, instance_id, guild=None):
        
        tz = Connector.get_timezone(instance_id)
        rem_type = Connector.get_reminder_type(instance_id)
        auto_delete = Connector.get_auto_delete(instance_id)
        experimental = Connector.is_experimental(instance_id)
        
        
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
        
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label='Experimental Features',
                custom_id='settings_experimental_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (experimental==False) else ButtonStyle.gray,
                label=f'Disabled',
                disabled=(experimental==False),
                custom_id=f'settings_experimental_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (experimental==True) else ButtonStyle.gray,
                label=f'Enabled',
                disabled=(experimental==True),
                custom_id=f'settings_experimental_enabled_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        action_rows.append(self.get_navigation_menu(instance_id, page=1))
        return action_rows
    
    def get_action_rows_page2(self, instance_id, guild=None):
        
        comm_mode = Connector.get_community_mode(instance_id)
        moderators = Connector.get_moderators(instance_id)

        action_rows = []
        
        if guild:
            # do not even show these to a DM session
            buttons = [
                manage_components.create_button(
                    style=ButtonStyle.blurple,
                    label=f'Community Mode',
                    custom_id='settings_community_nop'
                ),
                manage_components.create_button(
                    style=ButtonStyle.green if (comm_mode==Connector.CommunityMode.DISABLED) else ButtonStyle.gray,
                    label=f'Disabled',
                    disabled=(comm_mode==Connector.CommunityMode.DISABLED),
                    custom_id=f'settings_community_disabled_{instance_id}'
                ),
                manage_components.create_button(
                    style=ButtonStyle.green if (comm_mode==Connector.CommunityMode.ENABLED) else ButtonStyle.gray,
                    label=f'Enabled',
                    disabled=(comm_mode==Connector.CommunityMode.ENABLED),
                    custom_id=f'settings_community_enabled_{instance_id}'
                ),
                manage_components.create_button(
                    style=ButtonStyle.gray,
                    label=f'Configure ...',
                    disabled=(comm_mode==Connector.CommunityMode.DISABLED),
                    custom_id=f'settings_community_config_{instance_id}'
                )
            ]
            action_rows.append(manage_components.create_actionrow(*buttons))
        
            options = [
                manage_components.create_select_option(
                    label=role.name,
                    value=f'{role.id}',
                    default=(role.id in moderators)
                ) for role in guild.roles[:-25:-1]
            ]
            buttons = [
                manage_components.create_select(
                        custom_id=f'settings_moderator_{instance_id}',
                        placeholder='Select the Moderator Role(s)',
                        min_values=0,
                        max_values=len(options),
                        options=options
                )
            ]
            action_rows.append(manage_components.create_actionrow(*buttons))
        
        action_rows.append(self.get_navigation_menu(instance_id, page=2))
        return action_rows

    
    def get_action_rows_community(self, instance_id, guild=None):
        
        settings = Connector.get_community_settings(instance_id)
   
        action_rows = []
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Mods Only Mode',
                custom_id='settings_commset_modonly_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.mods_only==False) else ButtonStyle.gray,
                label=f'Disabled',
                disabled=(settings.mods_only==False),
                custom_id=f'settings_commset_modonly_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.mods_only==True) else ButtonStyle.gray,
                label=f'Enabled',
                disabled=(settings.mods_only==True),
                custom_id=f'settings_commset_modonly_enabled_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Repeating Reminders',
                custom_id='settings_commset_restrictrepeating_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_repeating==False) else ButtonStyle.gray,
                label=f'Everyone',
                disabled=(settings.restrict_repeating==False or settings.mods_only),
                custom_id=f'settings_commset_restrictrepeating_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_repeating==True) else ButtonStyle.gray,
                label=f'Mods Only',
                disabled=(settings.restrict_repeating==True or settings.mods_only),
                custom_id=f'settings_commset_restrictrepeating_enabled_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Mention @everyone',
                custom_id='settings_commset_everyone_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_everyone==False) else ButtonStyle.gray,
                label=f'Everyone',
                disabled=(settings.restrict_everyone==False or settings.mods_only),
                custom_id=f'settings_commset_everyone_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_everyone==True) else ButtonStyle.gray,
                label=f'Mods Only',
                disabled=(settings.restrict_everyone==True or settings.mods_only),
                custom_id=f'settings_commset_everyone_enabled_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.blurple,
                label=f'Remind other users',
                custom_id='settings_commset_foreign_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_foreign==False) else ButtonStyle.gray,
                label=f'Everyone',
                disabled=(settings.restrict_foreign==False or settings.mods_only),
                custom_id=f'settings_commset_foreign_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (settings.restrict_foreign==True) else ButtonStyle.gray,
                label=f'Mods Only',
                disabled=(settings.restrict_foreign==True or settings.mods_only),
                custom_id=f'settings_commset_foreign_enabled_{instance_id}'
            )
        ]
        action_rows.append(manage_components.create_actionrow(*buttons))
        
        
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.gray,
                label=f'Return',
                custom_id=f'settings_commset_return_{instance_id}_2'
            ),
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
        
        a_rows = self.get_action_rows_page1(instance_id, guild=ctx.guild)
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
            
            if not perms.administrator and \
                not perms.manage_guild and \
                not Connector.is_moderator(ctx.author.roles):
                await ctx.send('You need to have the `manage_server` or moderator permission to modify these settings', hidden=True)
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
        
        a_rows = self.get_action_rows_page1(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)
    
    
    async def set_autodel(self, ctx, args):
        
        if not args or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        new_type = args[0]
        instance_id = int(args[1])
        
        # perform permission checks for modifying settings
        # if author is User means that the command was invoked in DMs
        # there's no need for permission in DMs
        if isinstance(ctx.author, discord.Member):
            perms =  ctx.author.guild_permissions
            
            if not perms.administrator and \
                not perms.manage_guild and \
                not Connector.is_moderator(ctx.author.roles):

                await ctx.send('You need to have the `manage_server` or moderator permissions to modify these settings', hidden=True)
                return


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
        
        a_rows = self.get_action_rows_page1(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)
        
        
    async def set_community_mode(self, ctx, args):

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

        if new_type == 'disabled':
            new_enum = Connector.CommunityMode.DISABLED
        elif new_type == 'enabled':
            new_enum = Connector.CommunityMode.ENABLED
        elif new_type == 'config':
            # show the config file for the community mode instead
            #new_enum = Connector.CommunityMode.MODS_ONLY
            a_rows = self.get_action_rows_community(instance_id=instance_id, guild=ctx.guild)
            await ctx.edit_origin(components=a_rows)
            return
        else:
            return
        
        Connector.set_community_mode(instance_id, new_enum)
        
        a_rows = self.get_action_rows_page2(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)
    
    
    async def set_experimental(self, ctx, args):

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

        if new_type == 'disabled':
            new_mode = False
        elif new_type == 'enabled':
            new_mode = True
        else:
            return
        
        Connector.set_experimental(instance_id, new_mode)
        
        a_rows = self.get_action_rows_page1(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)
        
    

    async def set_moderators(self, ctx, args):
        
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
            
            
        new_mods = ctx.selected_options
        instance_id = int(args[0])
        
        Connector.set_moderators(instance_id, new_mods)        
        
        a_rows = self.get_action_rows_page2(instance_id=instance_id, guild=ctx.guild)
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

    async def set_modonly(self, ctx, args):
        
        if not args or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        # perform permission checks for modifying settings
        # if author is User means that the command was invoked in DMs
        # there's no need for permission in DMs
        if isinstance(ctx.author, discord.Member):
            perms =  ctx.author.guild_permissions
            
            if not perms.administrator and \
                not perms.manage_guild and \
                not Connector.is_moderator(ctx.author.roles):

                await ctx.send('You need to have the `manage_server` or moderator permission to modify these settings', hidden=True)
                return
        
        new_type = args[0]
        instance_id = int(args[1])

        
        new_settings = CommunitySettings.full_restricted()
        new_settings.mods_only = (new_type == 'enabled')
        
        Connector.set_community_settings(instance_id, new_settings)
        
        a_rows = self.get_action_rows_community(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)


    async def restrict_settings(self, ctx, args):
        
        if len(args) < 3 or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        # perform permission checks for modifying settings
        # if author is User means that the command was invoked in DMs
        # there's no need for permission in DMs
        if isinstance(ctx.author, discord.Member):
            perms =  ctx.author.guild_permissions
            
            if not perms.administrator and \
                not perms.manage_guild and \
                not Connector.is_moderator(ctx.author.roles):

                await ctx.send('You need to have the `manage_server` or moderator permission to modify these settings', hidden=True)
                return
        
        option = args[0]
        new_value = (args[1] == 'enabled')
        instance_id = int(args[2])

        # translate options into attribute name
        #
        # this is required, as _ is used as token for context id
        # but aswell as name for class attributes

        if option == 'restrictrepeating':
            attr_name = 'restrict_repeating'
        elif option == 'everyone':
            attr_name = 'restrict_everyone'
        elif option == 'foreign':
            attr_name = 'restrict_foreign'
        else:
            return
        
        Connector.set_community_setting(instance_id, attr_name, new_value)
        
        a_rows = self.get_action_rows_community(instance_id=instance_id, guild=ctx.guild)
        await ctx.edit_origin(components=a_rows)


    async def return_to_page(self, ctx, args):        
        if len(args) < 2 or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return
        
        instance_id = args[0]
        page = int(args[1])
        
        if page==1:
            a_rows = self.get_action_rows_page1(instance_id=instance_id, guild=ctx.guild)
        elif page==2:
            a_rows = self.get_action_rows_page2(instance_id=instance_id, guild=ctx.guild)

        await ctx.edit_origin(components=a_rows)
        
    async def navigate(self, ctx, args):
        
        if len(args) < 1 or args[0] == 'nop':
            await ctx.defer(edit_origin=True)
            return

        instance_id = args[0]
        page = ctx.selected_options[0]
        
        await self.return_to_page(ctx, [instance_id, page])

        

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
        elif args[1] == 'community':
            await self.set_community_mode(ctx, args[2:])
        elif args[1] == 'moderator':
            await self.set_moderators(ctx, args[2:])
        elif args[1] == 'commset':
            await self.switch_community_settings(ctx, args[2:])
        elif args[1] == 'experimental':
            await self.set_experimental(ctx, args[2:])
        elif args[1] == 'navigation':
            await self.navigate(ctx, args[2:])

   
    async def switch_community_settings(self, ctx: ComponentContext, args):

        if args[0] == 'return':
            await self.return_to_page(ctx, args[1:])
        elif args[0] == 'modonly':
            await self.set_modonly(ctx, args[1:])
        else:
            await self.restrict_settings(ctx, args)


    ##################
    # Commands methods
    ##################

    @cog_ext.cog_subcommand(base='settings', name='menu', description='Get an overview over all settings') 
    async def settings_menu_cmd(self, ctx):
        await self.show_settings_page(ctx)




def setup(client):
    client.add_cog(SettingsModule(client))