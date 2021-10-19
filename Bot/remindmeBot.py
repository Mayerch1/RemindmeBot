import os
import re
import discord
import asyncio

from discord.ext import commands, tasks
from discord_slash import SlashContext, SlashCommand, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Analytics import Analytics, Types


intents = discord.Intents()
intents.reactions = True
intents.messages = True
intents.guilds = True

token = os.getenv('BOT_TOKEN')
client = commands.Bot(command_prefix='/', description='Reminding you whenever you want', help_command=None, intents=intents)
slash = SlashCommand(client, sync_commands=True)


@client.event
async def on_slash_command_error(ctx, error):

    if isinstance(error, discord.ext.commands.errors.MissingPermissions):
        await ctx.send('You do not have permission to execute this command')
    elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await ctx.send('This command is only to be used on servers')
    elif isinstance(error, discord.NotFound):
        print(''.join(error.args))
        Analytics.register_exception(error)
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


@client.event
async def on_ready():
    # debug log
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('-----------')
    await client.change_presence(activity=discord.Game(name='/remindme'))
    
    update_community_count.start()
    update_experimental_count.start()


@client.event
async def on_guild_remove(guild):
    del_rem, del_intvl = Connector.delete_guild(guild.id)
    
    Analytics.guild_removed()
    Analytics.reminder_deleted(Types.DeleteAction.KICK, count=del_rem)
    Analytics.interval_deleted(Types.DeleteAction.KICK, count=del_intvl)

    print(f'removed from guild (total count: {len(client.guilds)})')


@client.event
async def on_guild_join(guild):

    # new guilds do not use the legacy mode
    Connector.set_legacy_interval(guild.id, False)

    Analytics.guild_added()
    guild_cnt = len(client.guilds)
    print(f'added to guild (total count: {guild_cnt})')

    if not guild.system_channel:
        return

    def is_round_number(x):
        while x%10 == 0 and x>0:
            x /= 10
        if x < 10:
            return True
        return False
    
    if is_round_number(guild_cnt):
        eb = discord.Embed(title=f'You\'re the {guild_cnt}th server I\'ve been added to', 
                        description='Here\'s a cool gif, just for you')
        eb.set_image(url='https://media.giphy.com/media/kyLYXonQYYfwYDIeZl/giphy.gif')
        await guild.system_channel.send(embed=eb)




@tasks.loop(hours=6)
async def update_experimental_count():
    
    comm_cnt = Connector.get_experimental_count()
    Analytics.experimental_count(comm_cnt)


@tasks.loop(hours=6)
async def update_community_count():
    
    comm_cnt = Connector.get_community_count()
    Analytics.community_count(comm_cnt)


@update_community_count.before_loop
async def update_community_count_before():
    await client.wait_until_ready()


@update_experimental_count.before_loop
async def update_experimental_count_before():
    await client.wait_until_ready()



def main():
    Connector.init()
    Analytics.init()

    client.load_extension(f'ReminderModule')
    client.load_extension(f'ReminderCreation')
    client.load_extension(f'ReminderListing')
    client.load_extension(f'HelpModule')
    client.load_extension(f'TimezoneModule')
    client.load_extension(f'AdminModule')
    client.load_extension(f'SettingsModule')

    client.load_extension(f'ServerCountPost')    

    client.run(token)


if __name__ == '__main__':
    main()
