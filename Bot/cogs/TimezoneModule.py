import re
import logging

from datetime import datetime
from dateutil import tz

import copy
import difflib
from datetime import datetime
from dateutil import tz
from dateutil.zoneinfo import getzoneinfofile_stream, ZoneInfoFile
from pytz import common_timezones as pytz_common_timezones, country_timezones

import discord

import lib.permissions
import util.interaction
from lib.CommunitySettings import CommunityAction
from lib.Connector import Connector
from lib.Analytics import Analytics


log = logging.getLogger('Remindme.Timezones')


class TimezoneModule(discord.Cog):

    ##################
    # Statics
    #################

    timezones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())


    settings_group = discord.SlashCommandGroup('settings', 'Change the config of this bot')
    
    def __init__(self, client):
        self.client = client
        
        self.timezone_country = {}
        for countrycode in country_timezones:
            timezones = country_timezones[countrycode]
            for timezone in timezones:
                self.timezone_country[timezone] = countrycode
    

    ################
    # autocomplete
    ################
     
    async def get_timezone_autocomplete(ctx: discord.AutocompleteContext):
        """Returns a list of colors that begin with the characters entered so far."""
        user_input = ctx.value.upper()
        return list(filter(lambda z: user_input in z.upper(), TimezoneModule.timezones)) # upper every iteration, to return case-sinsitive result to user


        
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
                        description=f'The timezone will be set to `{name}` (`UTC{offset}`)\n'\
                                    f'This corresponds to a local time of `{local_time}`\n'\
                                    f'{info_str}')

        return eb


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
    
    
    ################
    # idk whats that
    ################


    async def set_timezone(self, ctx: discord.ApplicationContext, instance_id: int, value: str):
        
        responded=False

        # tz lib will break on lower case utc
        re_utc = r'utc\+\d{1,2}'
        if re.match(re_utc, value):
            value = value.upper()

        tz_obj = tz.gettz(value)
        if not tz_obj:
            all_zones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())

            closest_tz = difflib.get_close_matches(value, all_zones, n=5)
            if not closest_tz:
                closest_tz = difflib.get_close_matches(value.upper(), all_zones, n=5)

            if value.upper() == 'PST':
                closest_tz = ['PST8PDT']  # manual override
            elif value.upper() == 'CST':
                closest_tz = ['CST6CDT']  # manual override
            elif value.upper() == 'MDT':
                closest_tz = ['MST7MDT']
            elif value.upper() == 'EDT':
                closest_tz = ['EST5EDT']
            
            # create a dropdown list
            options = [discord.SelectOption(
                    label=opt,
                    emoji='🔹' if opt in pytz_common_timezones else '🔸',
                    value=opt) for opt in closest_tz
                ]
            # hand the dropdown to managing class
            dd = discord.ui.Select(
                    placeholder='Select a timezone',
                    min_values=0,
                    max_values=1,
                    options=options
                )

            tz_eb = self._get_tz_error_eb(value)
            view = util.interaction.MulitDropdownView([dd])

            view.message = await ctx.respond(embed=tz_eb, view=view)
            responded = True
            await view.wait()

            value = view.value
            tz_obj = tz.gettz(value)


            if not value:
                # timeout
                return
            elif not tz_obj:
                # bug
                raise ValueError(f'User selected invalid timezone from dropdown {value}')


        tz_eb = self._get_tz_info_eb(tz_obj, value)
        view = util.interaction.ConfirmDenyView(dangerous_action=False)

        if not responded:
            view.message = await ctx.respond(embed=tz_eb, view=view)
        else:
            await ctx.edit(embed=tz_eb, view=view)

        await view.wait()
        if view.value:
            Connector.set_timezone(instance_id, value)
            Analytics.set_timezone(value, 
                                country_code=self.timezone_country.get(value, 'UNK'),
                                deprecated=value not in pytz_common_timezones)

        

    ################
    # Event methods
    ################

    @discord.Cog.listener()
    async def on_ready(self):
        log.info('TimezoneModule loaded')


    ##################
    # Commands methods
    ##################
    
    @settings_group.command(name='timezone', description='Set the timezone of this server') 
    async def set_timezone_sub_cmd(self, 
                                    ctx: discord.ApplicationContext, 
                                    new_timezone: discord.Option(
                                        str,
                                        "name of new timezone name",
                                        autocomplete=get_timezone_autocomplete
                                    )):

        # if no guild is present
        # assume dm context
        instance_id = ctx.guild.id if ctx.guild else ctx.author.id
        roles = ctx.author.roles if isinstance(ctx.author, discord.member.Member) else []

        if not lib.permissions.check_user_permission(instance_id, user_roles=roles, required_perms=CommunityAction(settings=True)):
            return

        await self.set_timezone(ctx, instance_id, new_timezone)


def setup(client):
    client.add_cog(TimezoneModule(client))