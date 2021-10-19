import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from bson import ObjectId

import copy
import difflib
from datetime import datetime
from dateutil import tz
from dateutil.zoneinfo import getzoneinfofile_stream, ZoneInfoFile
from pytz import common_timezones as pytz_common_timezones, country_timezones

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

import util.interaction
from lib.CommunitySettings import CommunitySettings, CommunityAction
from lib.Connector import Connector
from lib.Analytics import Analytics, Types


class TimezoneModule(commands.Cog):
    
    def __init__(self, client):
        self.client = client
        
        self.timezone_country = {}
        for countrycode in country_timezones:
            timezones = country_timezones[countrycode]
            for timezone in timezones:
                self.timezone_country[timezone] = countrycode
    
        
    ################
    # Helper methods
    ################
    
    def _get_tz_info_eb(self, zone, name):

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
            col = 0xcceb67  # light yellow

        # put new timezone into embed title
        # but make sure the title is not exceeding 256 chars
        eb = discord.Embed(title=f'New Timezone {name[:243]}',
                        color=col,
                        description=f'The timezone is now set to `{name}` (`UTC{offset}`)\n'\
                                    f'This corresponds to a local time of `{local_time}`\n'\
                                    f'{info_str}')

        return eb


    def _get_tz_info_str(self, zone, name):

        offset = datetime.now(zone).strftime('%z')
        out_str = f'Timezone is now set to `{name}` (`UTC{offset}`)'

        if re.match(r'^UTC\+\d+$', name):
            out_str += '\n• Consider using your local timezone (instead of `UTC+X`), in order to automatically adjust to daylight-saving*'
        elif name.lower() == 'mst':
            out_str += '\n• Consider using `MST7MDT` to respect daylight saving during winter'
        elif name.lower() == 'est':
            out_str += '\n• Consider using `EST5EDT` to respect daylight saving during winter'
        elif name not in pytz_common_timezones:
            out_str += f'\n• `{name}` seems to be a deprecated timezone and could be discontinued in future versions.\n'\
                    f'• Try and use a geo-referenced timezone that _observes_ `{name}` instead (e.g. `Europe/Berlin`)'

        return out_str


    def _get_tz_error_str(self, zone, closest_tz):

        err_str = 'The timezone `{:s}` is not valid'.format(zone)
        if closest_tz:
            err_str += '\nDid you mean `{:s}`?'.format('`, `'.join(closest_tz))

        err_str += '\n\nYou can have a look at all available timezones on this wikipedia list '\
                'https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'

        return err_str


    def _get_tz_error_eb(self, zone, no_list=False):
        
        select_str = '' if no_list else 'or select one from the list below'

        eb = discord.Embed(title='Invalid Timezone configuration',
                        color=0xde4b55,  # red-ish
                        description=f'The timezone `{zone}` is not valid\n'\
                                    f'Please re-invoke the command with a valid timezone '\
                                    f'{select_str}\n\n'\
                                    f'You can have a look at all available timezones on this '\
                                     '[wikipedia list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)')

        return eb
    
    
    def _get_tz_select_component(self, instance_id: int, tz_list: []):
        
        if tz_list:
            options = [
                manage_components.create_select_option(
                    label=opt,
                    emoji='🔹' if opt in pytz_common_timezones else '🔸',
                    value=opt) for opt in tz_list
            ]
            
            option_select = manage_components.create_select(
                custom_id=f'timezone_option_list_{instance_id}',
                placeholder='Select a proposed timezone',
                min_values=1,
                max_values=1,
                options=options
            )
            a_row = manage_components.create_actionrow(option_select)
            return [a_row]
        else:
            return []

    
    ################
    # idk whats that
    ################

    async def get_timezone(self, ctx, instance_id):
        await ctx.send('Timezone is set to `{:s}`'.format(Connector.get_timezone(instance_id)), hidden=True)



    async def set_timezone(self, ctx, instance_id, value):

        tz_obj = tz.gettz(value)
    
        if tz_obj:
            Connector.set_timezone(instance_id, value)
            Analytics.set_timezone(value, 
                                   country_code=self.timezone_country.get(value, 'UNK'),
                                   deprecated=value not in pytz_common_timezones)

            try:
                await ctx.send(embed=self._get_tz_info_eb(tz_obj, value))
            except discord.errors.Forbidden as e:
                await ctx.send(self._get_tz_info_str(tz_obj, value))

        else:
            all_zones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())
            closest_tz = difflib.get_close_matches(value, all_zones, n=5)
            
            if not closest_tz:
                closest_tz = difflib.get_close_matches(value.upper(), all_zones, n=5)

            if value.lower() == 'pst':
                closest_tz = ['PST8PDT']  # manual override
            elif value.lower() == 'cst':
                closest_tz = ['CST6CDT']  # manual override
            elif value.lower() == 'mdt':
                closest_tz = ['MST7MDT']
            elif value.lower() == 'edt':
                closest_tz = ['EST5EDT']
            
            comps = self._get_tz_select_component(instance_id, closest_tz)

            try:
                await ctx.send(embed=self._get_tz_error_eb(value, no_list=len(closest_tz)==0), components=comps, hidden=True)
            except discord.errors.Forbidden as e:
                await ctx.send(self._get_tz_error_str(value, closest_tz), hidden=True)


    ################
    # Event methods
    ################

    @commands.Cog.listener()
    async def on_ready(self):
        print('TimezoneModule loaded')
        
        
    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):

        if ctx.custom_id.startswith('timezone_option_list_'):
            id_split = ctx.custom_id.split('_')
            handle_id = int(id_split[-1])  # could be guild or user
            
            tz_str = ctx.selected_options[0]
            tz_obj = tz.gettz(tz_str)
            
            Connector.set_timezone(handle_id, tz_str)
            Analytics.set_timezone(tz_str, 
                                   country_code=self.timezone_country.get(tz_str, 'UNK'),
                                   deprecated=tz_str not in pytz_common_timezones)

            await ctx.send(embed=self._get_tz_info_eb(tz_obj, tz_str), hidden=True)

    ##################
    # Commands methods
    ##################
    
    @cog_ext.cog_subcommand(base='settings', name='timezone', description='Set the timezone of this server',
                        options=[
                            create_option(
                                name='new_timezone',
                                description='timezone name, when setting a new timezone',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            )
                        ]) 
    async def set_timezone_sub_cmd(self, ctx, new_timezone):

        # if no guild is present
        # assume dm context
        instance_id = ctx.guild.id if ctx.guild else ctx.author.id

        if not await util.interaction.check_user_permission(ctx, required_perms=CommunityAction(settings=True)):
            return

        await self.set_timezone(ctx, instance_id, new_timezone)


def setup(client):
    client.add_cog(TimezoneModule(client))