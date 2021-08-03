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

from ReminderModule import ReminderModule


intents = discord.Intents()
intents.reactions = True
intents.messages = True
intents.guilds = True

token = open('token.txt', 'r').read()
client = commands.Bot(command_prefix='/', description='Reminding you whenever you want', help_command=None, intents=intents)
slash = SlashCommand(client, sync_commands=False)

FEEDBACK_CHANNEL = 872104333007785984
FEEDBACK_MENTION = 872107119988588566


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


@client.slash.slash(name='help', description='Show the help page for this bot',
                    options=[
                        create_option(
                            name='page',
                            description='choose the subpage to display',
                            required=False,
                            option_type=SlashCommandOptionType.STRING,
                            choices=[
                                create_choice(
                                    name='overview',
                                    value='overview'
                                ),
                                create_choice(
                                    name='syntax',
                                    value='syntax'
                                ),
                                create_choice(
                                    name='timezones',
                                    value='timezones'
                                )
                            ]
                        )
                    ])
async def get_help(ctx, page='overview'):

    def get_overview_eb():

        embed = discord.Embed(title='Remindme Help', description='Reminding you whenever you want')

        embed.add_field(name='/help [page]', value='show the help page or choose a submenu [page]', inline=False)
        embed.add_field(name='/timezone', value='set/get the timezone of this server', inline=False)
        embed.add_field(name='/remindme', value='reminding you after a set time period', inline=False)
        embed.add_field(name='/remind', value='remind another user after a set time period', inline=False)
        embed.add_field(name='/reminder_list', value='manage all reminders of this server', inline=False)


        embed.add_field(name='\u200b', 
                        inline=False,
                        value='If you like this bot, you can leave a vote at [top.gg](https://top.gg/bot/831142367397412874).\n'\
                              'If you find a bug contact us on [Github](https://github.com/Mayerch1/RemindmeBot) on join the support server.')

        return embed

    def get_overview_str():
        return '**Remindme Help**\n'\
                '```Reminding you whenever you want\n'\
                '\n'\
                'help          Shows this message\n'\
                'timezone      set/get the timezone of this server\n'\
                'remindme      reminding you after a set time period\n'\
                'remind        remind another user after a set time period\n'\
                'reminder_list manage all your reminders for this server\n\n'\
                'please assign \'Embed Links\' permissions for better formatting```'

    def get_timezone_eb():

        eb = discord.Embed(title='Remindme Help', description='timezone help')

        eb.add_field(name='/timezone get', value='get the current timezone', inline=False)
        eb.add_field(name='/timezone set', value='set a new timezone', inline=False)

        eb.add_field(name='\u200B', 
                    value='• Allowed timezones are any strings defined by the IANA\n'\
                          '• Some timezones are marked as \'deprecated\' but can be used with a warning\n'\
                          '• geo-referencing timezones (e.g. `Europe/Berlin`) should be preferred\n'\
                          '  over more general (and deprecated) timezones (e.g. `CET`)', inline=False)

        eb.add_field(name='\u200b', value='If you like this bot, you can leave a vote at [top.gg](https://top.gg/bot/831142367397412874)', inline=False)

        return eb

    def get_timezone_str():
        return '**Remindme Help** - timezones\n'\
               '```'\
               '/timezone get     get the current timezone\n'\
               '/timezone set     set a new timezone\n\n'\
               '• Allowed timezones are any strings defined by the IANA\n'\
               '• Some timezones are marked as \'deprecated\' but can be used with a warning\n'\
               '• geo-referencing timezones (Europe/Berlin) should be preferred\n'\
               '  over more general (and deprecated) timezones (CET)'\
               '```'

    def get_syntax_eb():

        eb = discord.Embed(title='Remindme Help', 
                           description='This syntax is used whenever a user invokes `/remindme` or `/remind`\n'\
                                      f'{ReminderModule.REMIND_FORMAT_HELP}\n'\
                                      f'{ReminderModule.HELP_FOOTER}')
        
        return eb

    def get_syntax_str():
        return '**Remindme Help** - parser syntax and example usage' + ReminderModule.REMIND_FORMAT_HELP


    def get_help_components():
        buttons = [
            manage_components.create_button(
                style=ButtonStyle.URL,
                label='Invite Me',
                url='https://discord.com/oauth2/authorize?client_id=831142367397412874&permissions=84992&scope=bot%20applications.commands'
            ),
            manage_components.create_button(
                style=ButtonStyle.URL,
                label='Support Server',
                url='https://discord.gg/vH5syXfP'
            ),
            manage_components.create_button(
                style=ButtonStyle.gray,
                label='Direct Feedback',
                custom_id='help_direct_feedback'
            )
        ]

        return [manage_components.create_actionrow(*buttons)]

    

    comps = []

    if page == 'overview':
        eb = get_overview_eb()
        fallback = get_overview_str()
        comps = get_help_components()
    elif page == 'syntax':
        eb = get_syntax_eb()
        fallback = get_syntax_str()
    elif page == 'timezones':
        eb = get_timezone_eb()
        fallback = get_timezone_str()

    try:
        msg =await ctx.send(embed=eb, components=comps)
    except discord.errors.Forbidden:
        msg = await ctx.send(fallback)

    Analytics.help_page_called(page)


async def send_feedback(ctx):
    """give the user the option to send some quick
       feedback to the devs
    """

    dm = await ctx.author.create_dm()

    try:
        dm_test = await dm.send('*Direct Feedback*')
        channel = dm
    except discord.errors.Forbidden:
        dm_test = None
        channel = ctx.channel


    def msg_check(msg):
        return msg.author.id == ctx.author.id and msg.channel.id == channel.id

    q = await channel.send('If you want to send some feedback, '\
                       'just type a short sentence into the chat.\n'\
                       'Your feedback will be used to improve the bot')

    try:
        feedback = await client.wait_for('message', check=msg_check, timeout=2*60)
    except asyncio.exceptions.TimeoutError:
        # abort the deletion
        await q.delete()
        await dm_test.edit(content='*Direct Feedback* (timeout, please invoke again)') if dm_test else None
        return


    feedback_ch = client.get_channel(FEEDBACK_CHANNEL)

    if feedback_ch:
        feedback_str = f'<@&{FEEDBACK_MENTION}> New Feedback:\n'
        feedback_str += f'Author: {ctx.author.mention} ({ctx.author.name})\n\n'

        content = feedback.clean_content.replace('\n', '\n> ') # make sure multiline doesn't break quote style
        feedback_str += f'> {content}\n'
        await feedback_ch.send(feedback_str)
        await channel.send('Thanks for giving feedback to improve the bot')
    else:
        await channel.send('There was an issue when saving your feedback.\n'\
                           'Please report this bug on the *support server* or on *GitHub*')


@client.event
async def on_component(ctx: ComponentContext):

    if ctx.custom_id == 'help_direct_feedback':
        await ctx.defer(edit_origin=True)
        await send_feedback(ctx)


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
