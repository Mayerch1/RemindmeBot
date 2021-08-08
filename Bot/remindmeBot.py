import re
import discord
import asyncio

from discord.ext import commands
from discord_slash import SlashContext, SlashCommand, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

import difflib
from datetime import datetime
from dateutil import tz
from dateutil.zoneinfo import getzoneinfofile_stream, ZoneInfoFile

from pytz import common_timezones as pytz_common_timezones

from lib.Connector import Connector
from lib.Analytics import Analytics


intents = discord.Intents()
intents.reactions = True
intents.messages = True
intents.guilds = True

token = open('token.txt', 'r').read()
client = commands.Bot(command_prefix='/', description='Reminding you whenever you want', help_command=None, intents=intents)
slash = SlashCommand(client, sync_commands=False)


@client.event
async def on_slash_command_error(ctx, error):

    if isinstance(error, discord.ext.commands.errors.MissingPermissions):
        await ctx.send('You do not have permission to execute this command')
    elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await ctx.send('This command is only to be used on servers')
    else:
        print(error)
        Analytics.register_exception(error)
        raise error

@client.event
async def on_command_error(cmd, error):

    if isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await cmd.send('This command is only to be used on servers')
    elif isinstance(error, discord.ext.commands.errors.CommandNotFound):
        pass # silently catch these
    else:
        print(error)
        Analytics.register_exception(error)
        raise error



async def get_timezone(ctx, instance_id):
    await ctx.send('Timezone is set to `{:s}`'.format(Connector.get_timezone(instance_id)), hidden=True)


async def set_timezone(ctx, instance_id, value):

    def get_tz_error_str(zone, closest_tz):

        err_str = 'The timezone `{:s}` is not valid'.format(zone)
        if closest_tz:
            err_str += '\nDid you mean `{:s}`?'.format('`, `'.join(closest_tz))

        err_str += '\n\nYou can have a look at all available timezones on this wikipedia list '\
                  'https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'

        return err_str

    def get_tz_error_eb(zone, closest_tz):

        if closest_tz:
            tz_propose = 'Did you mean `{:s}`?'.format('`, `'.join(closest_tz))
        else:
            tz_propose = ''

        eb = discord.Embed(title='Invalid Timezone configuration',
                           color=0xde4b55,
                           description=f'The timezone `{zone}` is not valid\n'\
                                       f'{tz_propose}\n'\
                                       f'You can have a look at all available timezones on this wikipedia '\
                                        '[list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)')

        return eb


    def get_tz_info_str(zone, name):

        offset = datetime.now(zone).strftime('%z')
        out_str = f'Timezone is now set to `{name}` (`UTC{offset}`)'

        if re.match(r'^UTC\+\d+$', name):
            out_str += '\n• Consider using your local timezone (instead of `UTC+X`), in order to automatically adjust to daylight-saving*'
        elif name.lower() == 'mst':
            out_str += '\n• Consider using `MST7MDT` to respect daylight saving during winter'
        elif name.lower() == 'est':
            out_str += '\n• Consider using `EST5EDT` to respect daylight saving during winter'

        if name not in pytz_common_timezones:
            out_str += f'\n• `{name}` seems to be a deprecated timezone and could be discontinued in future versions.\n'\
                       f'• Try and use a geo-referenced timezone that _observes_ `{name}` instead (e.g. `Europe/Berlin`)'

        return out_str


    def get_tz_info_eb(zone, name):

        offset = datetime.now(zone).strftime('%z')
        local_time = datetime.now(zone).strftime('%H:%M')

        info_str = ''
        if re.match(r'^UTC\+\d+$', name):
            info_str += '\n• Consider using your local timezone (instead of `UTC+X`), in order to automatically adjust to daylight-saving*'
        elif name.lower() == 'mst':
            info_str += '\n• Consider using `MST7MDT` to respect daylight saving during winter'
        elif name.lower() == 'est':
            info_str += '\n• Consider using `EST5EDT` to respect daylight saving during winter'

        if name not in pytz_common_timezones:
            info_str += f'\n• `{name}` seems to be a deprecated timezone and could be discontinued in future versions.\n'\
                       f'• Try and use a geo-referenced timezone that _observes_ `{name}` instead (e.g. `Europe/Berlin`)'

        if not info_str:
            # no warnings means green embed
            col = 0x69eb67
        else:
            # some non-critical warnings will show slightly yellow embed
            col = 0xcceb67

        eb = discord.Embed(title='Timezone configuration',
                           color=col,
                           description=f'The timezone is now set to `{name}` (`UTC{offset}`)\n'\
                                       f'This corresponds to a local time of `{local_time}`\n'\
                                       f'{info_str}')
        
        return eb


    tz_obj = tz.gettz(value)
  
    if tz_obj:
        Connector.set_timezone(instance_id, value)

        try:
            await ctx.send(embed=get_tz_info_eb(tz_obj, value))
        except discord.errors.Forbidden as e:
            await ctx.send(get_tz_info_str(tz_obj, value))

    else:
        all_zones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())
        closest_tz = difflib.get_close_matches(value, all_zones, n=4)

        if value.lower() == 'pst':
            closest_tz = ['PST8PDT']  # manual override
        elif value.lower() == 'cst':
            closest_tz = ['CST6CDT']  # manual override

        try:
            await ctx.send(embed=get_tz_error_eb(value, closest_tz), hidden=True)
        except discord.errors.Forbidden as e:
            await ctx.send(get_tz_error_str(value, closest_tz), hidden=True)
        


@client.slash.slash(name='timezone', description='Set the timezone of this server',
                    options=[
                        create_option(
                            name='mode',
                            description='choose to get/set the timezone',
                            required=True,
                            option_type=SlashCommandOptionType.STRING,
                            choices=[
                                create_choice(
                                    name='get',
                                    value='get'
                                ),
                                create_choice(
                                    name='set',
                                    value='set'
                                )
                            ]

                        ),
                        create_option(
                            name='timezone',
                            description='string code for your time-zone, only when using set',
                            required=False,
                            option_type=SlashCommandOptionType.STRING
                        )
                    ]) 
async def set_timezone_cmd(ctx, mode, timezone=None):

    # if no guild is present
    # assume dm context
    if ctx.guild:
        instance_id = ctx.guild.id
    else:
        instance_id = ctx.author.id

    if mode == 'get':
        await get_timezone(ctx, instance_id)
    else:
        if not timezone:
            await ctx.send('You need to specify the `timezone` parameter for this `mode`', hidden=True)
            return

        await set_timezone(ctx, instance_id, timezone)


@client.event
async def on_ready():
    # debug log
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('-----------')
    await client.change_presence(activity=discord.Game(name='/remindme'))


@client.event
async def on_guild_remove(guild):
    Connector.delete_guild(guild.id)
    Analytics.guild_removed()
    print(f'removed from guild (total count: {len(client.guilds)})')


@client.event
async def on_guild_join(guild):
    Analytics.guild_added()
    guild_cnt = len(client.guilds)
    print(f'added to guild (total count: {guild_cnt})')

    if not guild.system_channel:
        return

    eb = discord.Embed(title=f'You\'re the {guild_cnt}th server I\'ve been added to', 
                       description='Here\'s a cool gif, just for you')
    eb.set_image(url='https://media.giphy.com/media/kyLYXonQYYfwYDIeZl/giphy.gif')

    if guild_cnt == 500 or (guild_cnt%1000) == 0:
        await guild.system_channel.send(embed=eb)


def main():
    Connector.init()
    Analytics.init()

    client.load_extension(f'TopGGModule')
    client.load_extension(f'DiscordBotListModule')
    client.load_extension(f'ReminderModule')
    client.load_extension(f'ReminderListing')
    client.load_extension(f'HelpModule')
    client.run(token)


if __name__ == '__main__':
    main()
