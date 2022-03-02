import os
import discord
from discord.ext import tasks
import logging
import traceback
import sys

from pathlib import Path
from discord.ext.help import Help, HelpElement, HelpPage
from discord.ext.servercount import ServerCount

from lib.Connector import Connector
from lib.Analytics import Analytics, Types

FEEDBACK_CHANNEL = 872104333007785984
FEEDBACK_MENTION = 872107119988588566


logging.basicConfig(level=logging.INFO) # general 3rd party

handler = logging.FileHandler(filename='./logs/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))

logging.getLogger('discord').setLevel(logging.WARNING) # reduce warning for discord lib

logging.getLogger('Remindme.Analytics').setLevel(logging.DEBUG)
logging.getLogger('Remindme.Timezones').setLevel(logging.DEBUG)
logging.getLogger('Remindme.Listing').setLevel(logging.DEBUG)
logging.getLogger('Remindme.Creation').setLevel(logging.DEBUG)
logging.getLogger('Remindme.Core').setLevel(logging.DEBUG)
logging.getLogger('Remindme.Admin').setLevel(logging.DEBUG)

# tmp verbosity
logging.getLogger('ext.servercount').setLevel(logging.DEBUG)

log = logging.getLogger('Remindme')
log.setLevel(logging.DEBUG) # own code

# root logger inherits handler to all other loggers
logging.getLogger().addHandler(handler)


token: str = os.getenv('BOT_TOKEN')
intents = discord.Intents.none()
intents.guilds = True # required for member roles -> permissions
#intents.reactions = True
#intents.messages = True

bot: discord.AutoShardedBot = discord.AutoShardedBot(intents=intents)

SYNTAX_HELP_PAGE = \
                'basic example:\n'\
                '> /remindme `time: 2d` `message: Hello World`\n'\
                '> /remind `target: @User` `time: 2d` `message: Hello World`\n'\
                '> /remind `target: @Role` `time: 2d` `message: Hello World`\n'\
                '\n'\
                'create repeating reminders\n'\
                '> /remindme `time: every friday at 14:15` `message: important appointment`\n'\
                '> /remindme `time: every other year at 2nd july` `message: interesting`\n'\
                '\n'\
                'combine relative intervals\n'\
                '```1y 1mo 2 days -5h```'\
                '\n'\
                'try different formats\n'\
                '```'\
                '• 5 jul, 5th july or july 5\n'\
                '• 3pm or 15:00\n'\
                '• every second monday each other month\n'\
                '• 2021-09-02T12:25:00+02:00\n'\
                '\n'\
                'Note: the parser uses day-first and year-least\n'\
                '      (01/02/03 -> 1st February 2003)\n'\
                '```'\
                '\n'\
                'use abbreviations for common terms\n'\
                '```'\
                '• eoy, eom, eow, eod - end of year/month/week/day\n'\
                '\n'\
                '• y(ears), mo(nths), w(eeks)\n'\
                '• d(ays), h(ours), m(ins)\n'\
                '\n'\
                'Note: eow is end of the working week (Friday Evening)\n'\
                '```'

# ###########
# Methods
# ###########
async def log_exception(ctx: discord.ApplicationContext, error: Exception):
    
    Analytics.register_exception(error)
    if isinstance(error, discord.NotFound):
        log.warning('interaction timed out (not found)')
    else:
        t = (type(error), error, error.__traceback__)
        log.error(''.join(traceback.format_exception(*t)))


# ###########
# Events
# ###########

@bot.event
async def on_ready():
    log.info('Logged in as')
    log.info(bot.user)
    log.info(bot.user.id)
    log.info('----------------')

    config_help()

    # await client.change_presence(activity=discord.Game(name='/remindme'))
    log.debug('starting base-file loops')
    update_community_count.start()
    update_experimental_count.start()


@bot.event
async def on_shard_connect(shard_id):
    log.debug(f'shard {shard_id} connected')


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: Exception):
    await log_exception(ctx, error)

    #     def get_err_embed(error_id):
#         eb = discord.Embed(title='An unknown error has ocurred', 
#                             description='The bot crashed while execution your command and we don\'t know why\n\n'\
#                                         'If you want to help improving this bot, '\
#                                         'please report this crash on the [support server](https://discord.gg/Xpyb9DX3D6)')
#         eb.color = 0xff0000  # red

#         eb.add_field(name='Error Code', value=str(error_id))
#         return eb

#     if isinstance(error, discord.ext.commands.errors.MissingPermissions):
#         await ctx.send('You do not have permission to execute this command')
#     elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
#         await ctx.send('This command is only to be used on servers')
#     elif isinstance(error, discord.NotFound):
#         print(''.join(error.args))
#         Analytics.register_exception(error)
#     else:
#         error_id = uuid.uuid4()
#         now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

#         print(f'{now_str}: UUID: {error_id}\n{error}')
#         Analytics.register_exception(error)
#         print('\n')

#         if not ctx.responded:
#             try:
#                 await ctx.send(embed=get_err_embed(error_id), hidden=True if not ctx.deferred else ctx._deferred_hidden)
#             except:
#                 # well...
#                 pass

#         raise error


@bot.event
async def on_error(event_method, *args, **kwargs):
    exc_info = sys.exc_info()
    log.critical('non-application error occurred', exc_info=exc_info)


# #############
# # Commands
# ############

def set_tokens():
    ServerCount.init(bot, 'fuelBot (https://github.com/Mayerch1/RemindmeBot)')
    ServerCount.set_token_dir('tokens')


def config_help():

    custom_footer = 'If you like this bot, you can leave a vote at [top.gg](https://top.gg/bot/831142367397412874).\n'\
                                'If you find a bug contact us on [Github](https://github.com/Mayerch1/RemindmeBot) or join the support server.'

    Help.init_help(bot, auto_detect_commands=True)

    Help.set_default_footer(custom_footer)
    Help.set_feedback(FEEDBACK_CHANNEL, FEEDBACK_MENTION)
    Help.invite_permissions(
        discord.Permissions(attach_files=True)
    )
    Help.support_invite('https://discord.gg/Xpyb9DX3D6')
    Help.set_tos_file('legal/tos.md')
    Help.set_privacy_file('legal/privacy.md')
    Help.set_github_url('https://github.com/Mayerch1/RemindmeBot')


    page = HelpPage(
        name='syntax',
        title='Syntax Help',
        emoji='✏️',
        description=SYNTAX_HELP_PAGE
    )
    Help.add_page(page)



# @client.event
# async def on_guild_remove(guild):
#     del_rem, del_intvl = Connector.delete_guild(guild.id)
    
#     Analytics.guild_removed()
#     Analytics.reminder_deleted(Types.DeleteAction.KICK, count=del_rem)
#     Analytics.interval_deleted(Types.DeleteAction.KICK, count=del_intvl)

#     print(f'removed from guild (total count: {len(client.guilds)})')


# @client.event
# async def on_guild_join(guild):

#     # new guilds do not use the legacy mode
#     Connector.set_legacy_interval(guild.id, False)

#     Analytics.guild_added()
#     guild_cnt = len(client.guilds)
#     print(f'added to guild (total count: {guild_cnt})')

#     if not guild.system_channel:
#         return

#     def is_round_number(x):
#         while x%10 == 0 and x>0:
#             x /= 10
#         if x < 10:
#             return True
#         return False
    
#     if is_round_number(guild_cnt):
#         eb = discord.Embed(title=f'You\'re the {guild_cnt}th server I\'ve been added to', 
#                         description='Here\'s a cool gif, just for you')
#         eb.set_image(url='https://media.giphy.com/media/kyLYXonQYYfwYDIeZl/giphy.gif')
#         await guild.system_channel.send(embed=eb)




@tasks.loop(hours=6)
async def update_experimental_count():
    
    log.debug('updating experimental server count')
    comm_cnt = Connector.get_experimental_count()
    Analytics.experimental_count(comm_cnt)


@tasks.loop(hours=3)
async def update_community_count():
    log.debug('updating anayltics guild/community count')

    comm_cnt = Connector.get_community_count()
    Analytics.community_count(comm_cnt)
    Analytics.guild_cnt(len(bot.guilds))


@update_community_count.before_loop
async def update_community_count_before():
    await bot.wait_until_ready()


@update_experimental_count.before_loop
async def update_experimental_count_before():
    await bot.wait_until_ready()



def main():
    Connector.init()
    Analytics.init()

    # client.load_extension(f'ReminderListing')
    # client.load_extension(f'TimezoneModule')
    # client.load_extension(f'ReminderCreation')
    # client.load_extension(f'AdminModule')

    # client.load_extension(f'HelpModule')
    # client.load_extension(f'ReminderModule')
    # client.load_extension(f'SettingsModule')

    for filename in os.listdir(Path(__file__).parent / 'cogs'):
        if filename.endswith('.py'):
            bot.load_extension(f'cogs.{filename[:-3]}')

    bot.load_extension('discord.ext.help.help')
    bot.load_extension('discord.ext.servercount.servercount')

    set_tokens()
    bot.run(token)




if __name__ == '__main__':
    main()

