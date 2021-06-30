import re
import discord

from discord.ext import commands
from discord_slash import SlashContext, SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType

import difflib
from dateutil import tz
from dateutil.zoneinfo import getzoneinfofile_stream, ZoneInfoFile

from lib.Connector import Connector
from lib.Analytics import Analytics


intents = discord.Intents()
intents.reactions = True
intents.messages = True
intents.guilds = True

token = open('token.txt', 'r').read()
client = commands.Bot(command_prefix='/', description='Reminding you whenever you want', help_command=None, intents=intents)
slash = SlashCommand(client, sync_commands=True, override_type=True)


@client.event
async def on_slash_command_error(ctx, error):

    if isinstance(error, discord.ext.commands.errors.MissingPermissions):
        await ctx.send('You do not have permission to execute this command')
    elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await ctx.send('This command is only to be used on servers')
    else:
        print(error)
        raise error


@client.event
async def on_command_error(cmd, error):

    if isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await cmd.send('This command is only to be used on servers')
    elif isinstance(error, discord.ext.commands.errors.CommandNotFound):
        pass # silently catch these
    else:
        print(error)
        raise error


async def get_timezone(ctx):
    await ctx.send('Timezone is set to `{:s}`'.format(Connector.get_timezone(ctx.guild.id)), hidden=True)


async def set_timezone(ctx, value):
    tz_obj = tz.gettz(value)

    if tz_obj:
        Connector.set_timezone(ctx.guild.id, value)

        out_str = 'Timezone is now set to `{:s}`'.format(value)
        if re.match(r'^UTC\+\d+$', value):
            out_str += '\n*Consider using your local timezone (instead of `UTC+X`), in order to automatically adjust to daylight-saving*'

        await ctx.send(out_str)
    else:

        err = True
        err_str = 'The timezone `{:s}` is not valid'.format(value)

        all_zones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())
        closest_tz = difflib.get_close_matches(value, all_zones)

        if closest_tz:
            err_str += '\nDid you mean `{:s}`?'.format('`, `'.join(closest_tz))

        await ctx.send(err_str, hidden=True)
        


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

    if not ctx.guild:
        await ctx.send('Setting the timezone is currently only supported on servers. Your private timezone is fixed to `UTC` (for now).')
        return

    if mode == 'get':
        await get_timezone(ctx)
    else:
        if not timezone:
            await ctx.send('You need to specify the `timezone` parameter for this `mode`', hidden=True)
            return

        await set_timezone(ctx, timezone)

@client.slash.slash(name='help', description='Show the help page for this bot')
async def get_help(ctx):

    embed = discord.Embed(title='Remindme Help', description='Reminding you whenever you want')

    embed.add_field(name='/help', value='show this message', inline=False)
    embed.add_field(name='/timezone', value='set/get the timezone of this server', inline=False)
    embed.add_field(name='/remindme', value='reminding you after a set time period', inline=False)
    embed.add_field(name='/remind', value='remind another user after a set time period', inline=False)
    embed.add_field(name='/reminder_list', value='manage all reminders of this server', inline=False)

    embed.add_field(name='\u200b', value='If you like this bot, you can leave a vote at [top.gg](https://top.gg/bot/831142367397412874)', inline=False)

    try:
        await ctx.send(embed=embed)
    except discord.errors.Forbidden:
        await ctx.send('```Reminding you whenever you want\n'\
                    '\n'\
                    'help          Shows this message\n'\
                    'timezone      set/get the timezone of this server\n'\
                    'remindme      reminding you after a set time period\n'\
                    'remind        remind another user after a set time period\n'\
                    'reminder_list manage all your reminders for this server\n\n'
                    'please assign \'Embed Links\' permissions for better formatting```')


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
    Analytics.delete_guild(guild.id)
    print(f'removed from guild (total count: {len(client.guilds)})')

@client.event
async def on_guild_join(guild):
    Analytics.add_guild(guild.id)
    print(f'added to guild (total count: {len(client.guilds)})')


def main():
    Connector.init()
    Analytics.init()

    client.load_extension(f'TopGGModule')
    client.load_extension(f'DiscordBotListModule')
    client.load_extension(f'ReminderModule')
    client.load_extension(f'ReminderListing')
    client.run(token)


if __name__ == '__main__':
    main()
