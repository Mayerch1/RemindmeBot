
import discord
from discord.ext import commands
from discord_slash import SlashContext, SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType

import difflib
from dateutil import tz
from dateutil.zoneinfo import getzoneinfofile_stream, ZoneInfoFile

from lib.Connector import Connector



token = open('token.txt', 'r').read()
client = commands.Bot(command_prefix='/', description='Reminding you whenever you want')
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
    else:
        print(error)
        raise error


async def get_timezone(cmd):
    await cmd.send('Timezone is set to `{:s}`'.format(Connector.get_timezone(cmd.guild.id)))


async def set_timezone(cmd, value):
    tz_obj = tz.gettz(value)

    if not tz_obj:
        err = True
        await cmd.send('The timezone `{:s}` is not valid'.format(value))
        all_zones = list(ZoneInfoFile(getzoneinfofile_stream()).zones.keys())
        closest_tz = difflib.get_close_matches(value, all_zones)
        if closest_tz:
            await cmd.send('Did you mean `{:s}`?'.format('`, `'.join(closest_tz)))

    # only save correct timezones
    if tz_obj:
        Connector.set_timezone(cmd.guild.id, value)
        await cmd.send('Timezone is now set to `{:s}`'.format(value))


@client.command(name='timezone', help='set the timezone of this server')
@commands.guild_only()
async def set_timezone_cmd(cmd, *value):

    if not value:
        await get_timezone(cmd)
    else:
        await set_timezone(cmd, value[0])

   




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



def main():
    Connector.init()

    client.load_extension(f'TopGGModule')
    client.load_extension(f'DiscordBotListModule')
    client.load_extension(f'ReminderModule')
    client.run(token)


if __name__ == '__main__':
    main()