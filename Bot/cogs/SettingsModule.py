import asyncio
import re
import logging

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

import util.interaction
from lib.Connector import Connector
from lib.CommunitySettings import CommunitySettings
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
    def __init__(self, scope: Connector.Scope, *args, **kwargs):
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
        eb = discord.Embed(title='Remindme Settings',
                description='Server Managers can edit these settings by pressing the '\
                            'corresponding buttons below.\n'\
                            'The grayed-out buttons are the current selected options.')
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
    def __init__(self, scope, page, page_callback, dropdown_row=4, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.scope:Connector.Scope = scope

        self.dd = MenuDropdown(page_num=page, page_switch_callback=page_callback, row=dropdown_row)
        self.add_item(self.dd)



class ExperimentalSettings(SettingsPageTemplate):
    def __init__(self, scope, page_callback, *args, **kwargs):
        super().__init__(scope=scope, page=2, page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()

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
        eb = discord.Embed(title='Remindme Settings',
                description='Server Managers can edit these settings by pressing the '\
                            'corresponding buttons below.\n'\
                            'The grayed-out buttons are the current selected options.')
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


class CommunitySettingsView(SettingsPageTemplate):
    def __init__(self, scope, page_callback, *args, **kwargs):
        super().__init__(scope=scope, page=1, page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()

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
        eb = discord.Embed(title='Remindme Settings',
                description='Server Managers can edit these settings by pressing the '\
                            'corresponding buttons below.\n'\
                            'The grayed-out buttons are the current selected options.')
        return eb
    

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

    # TODO: moderator dropdown



class BaseSettings(SettingsPageTemplate):
    def __init__(self, scope, page_callback, *args, **kwargs):
        super().__init__(scope=scope, page=0, page_callback=page_callback, dropdown_row=4, *args, **kwargs)
        self.update_ui_elements()


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

        self.view:SettingsPageTemplate = self._page_lookup(page)(scope=scope, page_callback=self.page_switch)
        

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
            new_view = self._page_lookup(new_page)(scope=self.scope, page_callback=self.page_switch, message=self.view.message)

            # stop the old view and replac with new one
            message = self.view.message
            self.view.stop()
            self.view = new_view

            await message.edit_original_message(embed=self.view.get_embed(), view=self.view)


class SettingsModule(commands.Cog):
    
    ##################
    # Statics
    #################

    settings_group = discord.SlashCommandGroup('st', 'Change the config of this bot', guild_ids=[140150091607441408])

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
            ),
            manage_components.create_select_option(
                label='Experimental Page',
                description='Show new/test settings',
                value='3',
                emoji='🥼',
                default=(page==3)
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
        legacy = Connector.is_legacy_interval(instance_id)
        
        
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
                label='Interval Parsing',
                custom_id='settings_legacy_nop'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (legacy==False) else ButtonStyle.gray,
                label=f'Follow Timezone',
                disabled=(legacy==False),
                custom_id=f'settings_legacy_disabled_{instance_id}'
            ),
            manage_components.create_button(
                style=ButtonStyle.green if (legacy==True) else ButtonStyle.gray,
                label=f'Legacy (always UTC)',
                disabled=(legacy==True),
                custom_id=f'settings_legacy_enabled_{instance_id}'
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


    def get_action_rows_page3(self, instance_id, guild=None):

        experimental = Connector.is_experimental(instance_id)

        action_rows = []
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
        
        action_rows.append(self.get_navigation_menu(instance_id, page=3))
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

    async def show_settings_page(self, ctx):
        
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
        
    async def set_legacy_intervals(self, ctx, args):

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

        if new_type == 'enabled':
            new_mode = True
            eb = discord.Embed(title='Legacy Interval Parsing Mode', 
                        description='All future **and existing** intervals are interpreted as in *UTC*, independent of the server time')
            eb.color = 0xcceb67  # light yellow
        elif new_type == 'disabled':
            new_mode = False
            eb = discord.Embed(title='New Interval Parsing Mode', 
                        description='All future **and existing** intervals are now interpreted in your local timezone')
            eb.color = 0x69eb67  # light green
        else:
            # timeout the interaction
            return


        
        try:
            await ctx.channel.send(embed=eb)
        except:
            # just don't inform the user on failure
            # do nothing in DMs or threads
            pass

        Connector.set_legacy_interval(instance_id, new_mode)
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
        elif page==3:
            a_rows = self.get_action_rows_page3(instance_id=instance_id, guild=ctx.guild)

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
        log.info('loaded')
        
        
    # @commands.Cog.listener()
    # async def on_component(self, ctx: ComponentContext):
        
    #     args = ctx.custom_id.split('_')
        
    #     # args 0 must exists
    #     if args[0] != 'settings' or len(args) < 2:
    #         return
        
    #     if args[1] == 'type':
    #         await self.set_reminder_type(ctx, args[2:])
    #     elif args[1] == 'timezone':
    #         await self.show_timezone_hint(ctx, args[2:])
    #     elif args[1] == 'autodel':
    #         await self.set_autodel(ctx, args[2:])
    #     elif args[1] == 'community':
    #         await self.set_community_mode(ctx, args[2:])
    #     elif args[1] == 'moderator':
    #         await self.set_moderators(ctx, args[2:])
    #     elif args[1] == 'commset':
    #         await self.switch_community_settings(ctx, args[2:])
    #     elif args[1] == 'experimental':
    #         await self.set_experimental(ctx, args[2:])
    #     elif args[1] == 'legacy':
    #         await self.set_legacy_intervals(ctx, args[2:])
    #     elif args[1] == 'navigation':
    #         await self.navigate(ctx, args[2:])

   
    # async def switch_community_settings(self, ctx: ComponentContext, args):

    #     if args[0] == 'return':
    #         await self.return_to_page(ctx, args[1:])
    #     elif args[0] == 'modonly':
    #         await self.set_modonly(ctx, args[1:])
    #     else:
    #         await self.restrict_settings(ctx, args)


    ##################
    # Commands methods
    ##################

    @settings_group.command(name='menu', description='Get an overview over all settings') 
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