import asyncio
import re
import logging
from typing import Union

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

from util.consts import Consts
import lib.permissions
import util.interaction
from lib.Connector import Connector
from lib.CommunitySettings import CommunitySettings, CommunityAction
from lib.Analytics import Analytics, Types


log = logging.getLogger('Remindme.Settings')

class MenuDropdown(discord.ui.Select):
    def __init__(self, page_num: int, page_switch_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.page_callback=page_switch_callback
        self.placeholder='Select a Menu page'
        self.min_values=1
        self.max_values=1

        self.page = page_num
        self.next_page = page_num

        opts = [
            discord.SelectOption(label='Basic Page', emoji='🌐', description='Holds most important settings', value='0', default=(page_num==0)),
            discord.SelectOption(label='Community Page', emoji='👪', description='Show community related settings', value='1', default=(page_num==1)),
            discord.SelectOption(label='Experimental Page', emoji='🥼', description='Show new/test settings', value='2', default=(page_num==2)),
        ]
        self.options = opts


    async def callback(self, interaction: discord.Interaction):
        if self.values:
            self.next_page = int(self.values[0])
            await self.page_callback(interaction)


class CommunitySubSettings(util.interaction.CustomView):
    def __init__(self, scope: Connector.Scope, roles=[], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scope = scope
        self.update_ui_elements()
        


    def update_ui_elements(self):
        comm_settings = Connector.get_community_settings(self.scope.instance_id)


        if comm_settings.restrict_repeating:
            self.repeat_everyone.style = discord.ButtonStyle.secondary
            self.repeat_everyone.disabled = False
            self.repeat_mods.style = discord.ButtonStyle.success
            self.repeat_mods.disabled = True
        else:
            self.repeat_everyone.style = discord.ButtonStyle.success
            self.repeat_everyone.disabled = True
            self.repeat_mods.style = discord.ButtonStyle.secondary
            self.repeat_mods.disabled = False

        if comm_settings.restrict_everyone:
            self.mention_everyone.style = discord.ButtonStyle.secondary
            self.mention_everyone.disabled = False
            self.mention_mods.style = discord.ButtonStyle.success
            self.mention_mods.disabled = True
        else:
            self.mention_everyone.style = discord.ButtonStyle.success
            self.mention_everyone.disabled = True
            self.mention_mods.style = discord.ButtonStyle.secondary
            self.mention_mods.disabled = False

        if comm_settings.restrict_foreign:
            self.foreign_everyone.style = discord.ButtonStyle.secondary
            self.foreign_everyone.disabled = False
            self.foreign_mods.style = discord.ButtonStyle.success
            self.foreign_mods.disabled = True
        else:
            self.foreign_everyone.style = discord.ButtonStyle.success
            self.foreign_everyone.disabled = True
            self.foreign_mods.style = discord.ButtonStyle.secondary
            self.foreign_mods.disabled = False


        if comm_settings.mods_only:
            # force all buttons to off for community mode
            # colors are already set from above
            self.repeat_everyone.disabled=True
            self.repeat_mods.disabled=True
            self.mention_everyone.disabled=True
            self.mention_mods.disabled=True
            self.foreign_everyone.disabled=True
            self.foreign_mods.disabled=True

            # mod buttons
            self.mod_enabled.style=discord.ButtonStyle.success
            self.mod_enabled.disabled=True
            self.mod_disabled.style=discord.ButtonStyle.secondary
            self.mod_disabled.disabled=False
        else:
            # mod buttons
            self.mod_enabled.style=discord.ButtonStyle.secondary
            self.mod_enabled.disabled=False
            self.mod_disabled.style=discord.ButtonStyle.success
            self.mod_disabled.disabled=True


    def get_embed(self) -> discord.Embed:
        eb = discord.Embed(title='Remindme Community-Settings',
                description='This page allows moderators to restrict certain features to moderators.\n'\
                            'In "Mods-Only" mode, the bot is only usable by moderators')
        return eb
    

    async def send_update_ui(self, interaction: discord.Interaction):
        self.update_ui_elements()
        await interaction.response.edit_message(view=self)



    @discord.ui.button(label='Mods Only Mode', style=discord.ButtonStyle.primary, row=0)
    async def mods_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Disabled', style=discord.ButtonStyle.secondary, row=0)
    async def mod_disabled(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'mods_only', False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Enabled', style=discord.ButtonStyle.secondary, row=0)
    async def mod_enabled(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_settings(self.scope.instance_id, CommunitySettings.full_restricted())
        await self.send_update_ui(interaction)



    @discord.ui.button(label='Repeating Reminders', style=discord.ButtonStyle.primary, row=1)
    async def repeating_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Everyone', style=discord.ButtonStyle.secondary, row=1)
    async def repeat_everyone(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_repeating', False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Mods Only', style=discord.ButtonStyle.secondary, row=1)
    async def repeat_mods(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_repeating', True)
        await self.send_update_ui(interaction)



    @discord.ui.button(label='Mention @everyone', style=discord.ButtonStyle.primary, row=2)
    async def mention_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed
    @discord.ui.button(label='Everyone', style=discord.ButtonStyle.secondary, row=2)
    async def mention_everyone(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_everyone', False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Mods Only', style=discord.ButtonStyle.secondary, row=2)
    async def mention_mods(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_everyone', True)
        await self.send_update_ui(interaction)


    
    @discord.ui.button(label='Remind other users', style=discord.ButtonStyle.primary, row=3)
    async def foreign_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Everyone', style=discord.ButtonStyle.secondary, row=3)
    async def foreign_everyone(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_foreign', False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Mods Only', style=discord.ButtonStyle.secondary, row=3)
    async def foreign_mods(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_setting(self.scope.instance_id, 'restrict_foreign', True)
        await self.send_update_ui(interaction)


    @discord.ui.button(label='Return', style=discord.ButtonStyle.secondary, row=4)
    async def ret_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.disable_all()
        await interaction.response.edit_message(view=self) # in case of timeout
        self.stop()

class SettingsPageTemplate(util.interaction.CustomView):
    def __init__(self, scope, page, page_callback, dropdown_row=4, roles=[], *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.scope:Connector.Scope = scope

        self.dd = MenuDropdown(page_num=page, page_switch_callback=page_callback, row=dropdown_row)
        self.add_item(self.dd)



class ExperimentalSettings(SettingsPageTemplate):
    def __init__(self, scope, author: Union[discord.User, discord.Member], guild_roles: list[discord.Role], page_callback, *args, **kwargs):
        super().__init__(scope=scope, page=2, page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()

        action = CommunityAction(settings=True)
        self.forbidden = not lib.permissions.check_user_permission(self.scope.instance_id, author.roles, required_perms=action)

        if scope.is_private or (self.forbidden and not author.guild_permissions.administrator):
            self.disable_all()
            self.dd.disabled = False


    def update_ui_elements(self):
        is_exp = Connector.is_experimental(self.scope.instance_id)

        if is_exp:
            self.exp_enabled.style=discord.ButtonStyle.success
            self.exp_enabled.disabled=True
            self.exp_disabled.style=discord.ButtonStyle.secondary
            self.exp_disabled.disabled=False
        else:
            self.exp_enabled.style=discord.ButtonStyle.secondary
            self.exp_enabled.disabled=False
            self.exp_disabled.style=discord.ButtonStyle.success
            self.exp_disabled.disabled=True


    def get_embed(self) -> discord.Embed:
        eb = discord.Embed(title='Remindme Experimental-Settings',
                description='Server Managers can enable experimental settings.\n'\
                            'These are new features which are not yet ready to be deployed for everyone.\n'\
                            'Be aware that the Bot might not be as reliable with these turned on.')
        
        if self.forbidden:
            eb.color = Consts.col_err
            eb.description = 'You do not have permissions to modify the community settings of this server. Only moderators can do so.'

        return eb
    

    async def send_update_ui(self, interaction: discord.Interaction):
        self.update_ui_elements()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Experimental Features', style=discord.ButtonStyle.primary, row=0)
    async def experimental_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Disabled', style=discord.ButtonStyle.secondary, row=0)
    async def exp_disabled(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_experimental(self.scope.instance_id, False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Enabled', style=discord.ButtonStyle.secondary, row=0)
    async def exp_enabled(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_experimental(self.scope.instance_id, True)
        await self.send_update_ui(interaction)


class RoleDropDown(discord.ui.Select):
    def __init__(self, scope: Connector.Scope, author: Union[discord.User, discord.Member], guild_roles: list[discord.Role], mod_roles: list[int], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.scope=scope
        self.placeholder='Select the Moderator Role(s)'
        
        self.guild_roles = guild_roles[::-1][:25] # only show the "highest" 25
        self.author = author
        self.mod_roles = mod_roles

        opts = [
            discord.SelectOption(label=r.name[:25], value=str(r.id), default=r.id in self.mod_roles) for r in self.guild_roles
        ]
        self.options = opts

        self.min_values=0
        self.max_values=len(self.options)


    async def callback(self, interaction: discord.Interaction):
        self.mod_roles = list(map(int, self.values))
        log.debug(f'updated moderator count is {len(self.mod_roles)}')
        Connector.set_moderators(self.scope.instance_id, self.mod_roles)


class CommunitySettingsView(SettingsPageTemplate):
    def __init__(self, scope:Connector.Scope, author: Union[discord.User, discord.Member], guild_roles: list[discord.Role], page_callback, *args, **kwargs):
        super().__init__(scope, page=1, page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()

        self.guild_roles = guild_roles
        self.author = author

        mod_roles = Connector.get_moderators(self.scope.instance_id)

        self.role_drop = RoleDropDown(scope=scope, author=self.author, guild_roles=self.guild_roles, mod_roles=mod_roles)
        self.add_item(self.role_drop)

        action = CommunityAction(settings=True)
        self.forbidden = not lib.permissions.check_user_permission(self.scope.instance_id, self.author.roles, required_perms=action)

        if scope.is_private or (self.forbidden and not self.author.guild_permissions.administrator):
            self.disable_all()
            self.dd.disabled = False


    def update_ui_elements(self):
        comm_mode = Connector.get_community_mode(self.scope.instance_id)

        if comm_mode == Connector.CommunityMode.ENABLED:
            self.mode_enabled.style=discord.ButtonStyle.success
            self.mode_enabled.disabled=True
            self.mode_disablde.style=discord.ButtonStyle.secondary
            self.mode_disablde.disabled=False

            self.mode_config.disabled = False
        else:
            self.mode_enabled.style=discord.ButtonStyle.secondary
            self.mode_enabled.disabled=False
            self.mode_disablde.style=discord.ButtonStyle.secondary
            self.mode_disablde.disabled=True

            self.mode_config.disabled = True


    def get_embed(self) -> discord.Embed:
        eb = discord.Embed(title='Remindme Community-Settings',
                description='Server Managers can toggle the community mode, aswell as declare new moderators for this bot.'\
                            'The restrictions in community modes can be specified in "Config..."')

        if self.forbidden:
            eb.color = Consts.col_err
            eb.description = 'You do not have permissions to modify the community settings of this server. Only moderators can do so.'

        return eb


    def get_denied_embed(self) -> discord.Embed:
        return discord.Embed(title='Missing Permissions',
                                description='You are missing the privileges to modify the community settings of this bot',
                                color=Consts.col_err)

    async def send_update_ui(self, interaction: discord.Interaction):
        self.update_ui_elements()
        await interaction.response.edit_message(view=self)


    @discord.ui.button(label='Community Mode', style=discord.ButtonStyle.primary, row=0)
    async def community_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Disabled', style=discord.ButtonStyle.secondary, row=0)
    async def mode_disablde(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_mode(self.scope.instance_id, Connector.CommunityMode.DISABLED)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Enabled', style=discord.ButtonStyle.secondary, row=0)
    async def mode_enabled(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_community_mode(self.scope.instance_id, Connector.CommunityMode.ENABLED)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Configure...', style=discord.ButtonStyle.secondary, row=0)
    async def mode_config(self, button: discord.ui.Button, interaction: discord.Interaction):

        view = CommunitySubSettings(self.scope, message=self.message)
        eb = view.get_embed()
        await interaction.response.edit_message(embed=eb, view=view)

        await view.wait()
        self.message = view.message

        eb = self.get_embed()
        self.update_ui_elements()
        await self.message.edit_original_message(embed=eb, view=self)


    @discord.ui.button(label='Moderators:', style=discord.ButtonStyle.secondary, row=1)
    async def mod_placeholder_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing



class BaseSettings(SettingsPageTemplate):
    def __init__(self, scope: Connector.Scope, author: Union[discord.User, discord.Member], guild_roles: list[discord.Role], page_callback, *args, **kwargs):
        super().__init__(scope=scope, page=0, roles=[], page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()

        action = CommunityAction(settings=True)
        self.forbidden = not lib.permissions.check_user_permission(self.scope.instance_id, author.roles, required_perms=action)

        if scope.is_private or (self.forbidden and not author.guild_permissions.administrator):
            self.disable_all()
            self.dd.disabled = False


    def update_ui_elements(self):
        self.server_tz_val.label = Connector.get_timezone(self.scope.instance_id)
        rem_type = Connector.get_reminder_type(self.scope.instance_id)
        del_type = Connector.get_auto_delete(self.scope.instance_id)
        parse_legacy = Connector.is_legacy_interval(self.scope.instance_id)

        

        if rem_type==Connector.ReminderType.HYBRID:
            self.style_hybrid.style=discord.ButtonStyle.success
            self.style_hybrid.disabled=True
            self.style_embed.style=discord.ButtonStyle.secondary
            self.style_embed.disabled=False
            self.style_text.style=discord.ButtonStyle.secondary
            self.style_text.disabled=False
        elif rem_type==Connector.ReminderType.EMBED_ONLY:
            self.style_hybrid.style=discord.ButtonStyle.secondary
            self.style_hybrid.disabled=False
            self.style_embed.style=discord.ButtonStyle.success
            self.style_embed.disabled=True
            self.style_text.style=discord.ButtonStyle.secondary
            self.style_text.disabled=False
        else:
            self.style_hybrid.style=discord.ButtonStyle.secondary
            self.style_hybrid.disabled=False
            self.style_embed.style=discord.ButtonStyle.secondary
            self.style_embed.disabled=False
            self.style_text.style=discord.ButtonStyle.success
            self.style_text.disabled=True

        if del_type==Connector.AutoDelete.NEVER:
            self.del_never.style=discord.ButtonStyle.success
            self.del_never.disabled=True
            self.del_timeout.style=discord.ButtonStyle.secondary
            self.del_timeout.disabled=False
            self.del_hidden.style=discord.ButtonStyle.secondary
            self.del_hidden.disabled=False
        elif del_type==Connector.AutoDelete.TIMEOUT:
            self.del_never.style=discord.ButtonStyle.secondary
            self.del_never.disabled=False
            self.del_timeout.style=discord.ButtonStyle.success
            self.del_timeout.disabled=True
            self.del_hidden.style=discord.ButtonStyle.secondary
            self.del_hidden.disabled=False
        else:
            self.del_never.style=discord.ButtonStyle.secondary
            self.del_never.disabled=False
            self.del_timeout.style=discord.ButtonStyle.secondary
            self.del_timeout.disabled=False
            self.del_hidden.style=discord.ButtonStyle.success
            self.del_hidden.disabled=True

        if parse_legacy:
            self.parse_legacy.style=discord.ButtonStyle.success
            self.parse_legacy.disabled=True
            self.parse_local.style=discord.ButtonStyle.secondary
            self.parse_local.disabled=False
        else:
            self.parse_legacy.style=discord.ButtonStyle.secondary
            self.parse_legacy.disabled=False
            self.parse_local.style=discord.ButtonStyle.success
            self.parse_local.disabled=True


    def get_embed(self) -> discord.Embed:
        eb = discord.Embed(title='Remindme Settings',
                description='Server Managers can edit these settings by pressing the '\
                            'corresponding buttons below.\n'\
                            'The grayed-out buttons are the current selected options.')

        if self.forbidden:
            eb.color = Consts.col_err
            eb.description = 'You do not have permissions to modify the community settings of this server. Only moderators can do so.'

        return eb
    

    async def send_update_ui(self, interaction: discord.Interaction):
        self.update_ui_elements()
        await interaction.response.edit_message(view=self)

    
    
    @discord.ui.button(label='Server Timezone', style=discord.ButtonStyle.primary, row=0)
    async def server_tz(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='UTC', style=discord.ButtonStyle.secondary, row=0)
    async def server_tz_val(self, button: discord.ui.Button, interaction: discord.Interaction):
        # show timezone embed
        eb = SettingsModule.get_tz_info_eb(Connector.get_timezone(self.scope.instance_id))
        await interaction.response.send_message(embed=eb, ephemeral=True)


    @discord.ui.button(label='Preferred Reminder Style', style=discord.ButtonStyle.primary, row=1)
    async def reminder_style(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed
    @discord.ui.button(label='Hybrid Reminders', style=discord.ButtonStyle.secondary, row=1)
    async def style_hybrid(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_reminder_type(self.scope.instance_id, Connector.ReminderType.HYBRID)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Embed-Only Reminders', style=discord.ButtonStyle.secondary, row=1)
    async def style_embed(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_reminder_type(self.scope.instance_id, Connector.ReminderType.EMBED_ONLY)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Text-Only Reminders', style=discord.ButtonStyle.secondary, row=1)
    async def style_text(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_reminder_type(self.scope.instance_id, Connector.ReminderType.TEXT_ONLY)
        await self.send_update_ui(interaction)


    @discord.ui.button(label='Delete Creation Style', style=discord.ButtonStyle.primary, row=2)
    async def delete_style(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Delete after Timeout', style=discord.ButtonStyle.secondary, row=2)
    async def del_timeout(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_auto_delete(self.scope.instance_id, Connector.AutoDelete.TIMEOUT)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Never Delete', style=discord.ButtonStyle.secondary, row=2)
    async def del_never(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_auto_delete(self.scope.instance_id, Connector.AutoDelete.NEVER)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Only Show to author', style=discord.ButtonStyle.secondary, row=2)
    async def del_hidden(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_auto_delete(self.scope.instance_id, Connector.AutoDelete.HIDE)
        await self.send_update_ui(interaction)


    @discord.ui.button(label='Interval Parsing', style=discord.ButtonStyle.primary, row=3)
    async def parsing_style(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass # do nothing when this one is pressed

    @discord.ui.button(label='Use local Timezone', style=discord.ButtonStyle.secondary, row=3)
    async def parse_local(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_legacy_interval(self.scope.instance_id, False)
        await self.send_update_ui(interaction)

    @discord.ui.button(label='Legacy (always UTC)', style=discord.ButtonStyle.secondary, row=3)
    async def parse_legacy(self, button: discord.ui.Button, interaction: discord.Interaction):
        Connector.set_legacy_interval(self.scope.instance_id, True)
        await self.send_update_ui(interaction)


class SettingsManager():
    def __init__(self, ctx: discord.ApplicationContext, scope, page, *args, **kwargs):
        
        self.scope = scope
        self.ctx = ctx

        self.roles = ctx.guild.roles if ctx.guild else []

        self.view:SettingsPageTemplate = self._page_lookup(page)(scope=scope, author=ctx.author, guild_roles=self.roles, page_callback=self.page_switch)
        

    def _page_lookup(self, page: int) -> SettingsPageTemplate:
        lut = {
            0: BaseSettings,
            1: CommunitySettingsView,
            2: ExperimentalSettings
        }
        if page in lut:
            return lut[page]
        else:
            raise ValueError(f'Unsupported Page number {page}')


    async def send(self):
        eb = self.view.get_embed()
        msg = await self.ctx.respond(embed=eb, view=self.view, ephemeral=True)
        self.view.message = msg



    async def page_switch(self, interaction: discord.Interaction):
        if self.view.dd.page != self.view.dd.next_page:
            # get view based on next page
            new_page = int(self.view.dd.next_page)
            new_view = self._page_lookup(new_page)(scope=self.scope, author=self.ctx.author, guild_roles=self.roles, page_callback=self.page_switch, message=self.view.message)

            # stop the old view and replac with new one
            message = self.view.message
            self.view.stop()
            self.view = new_view

            await message.edit_original_message(embed=self.view.get_embed(), view=self.view)


class SettingsModule(commands.Cog):
    
    ##################
    # Statics
    #################

    def __init__(self, client):
        self.client = client

        
    ################
    # Helper methods
    ################
    
    @staticmethod
    def get_tz_info_eb(name):
        
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



    ################
    # Event methods
    ################

    @commands.Cog.listener()
    async def on_ready(self):
        log.info('loaded')

    
    ##################
    # Commands methods
    ##################


    @commands.slash_command(name='settings', description='Get an overview over all settings') 
    async def settings_menu_cmd(self, ctx):
        
        scope = Connector.Scope(
            is_private=(not ctx.guild),
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id = ctx.author.id
        )


        sets = SettingsManager(ctx=ctx, scope=scope, page=0)
        await sets.send()




def setup(client):
    client.add_cog(SettingsModule(client))