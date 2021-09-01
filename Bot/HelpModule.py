import asyncio

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Analytics import Analytics

FEEDBACK_CHANNEL = 872104333007785984
FEEDBACK_MENTION = 872107119988588566

class HelpModule(commands.Cog):
    
    SYNTAX_HELP_PAGE = \
                'basic example:\n'\
                '> /remindme `time: 2d` `message: Hello World`\n'\
                '\n'\
                'remind other users and roles\n'\
                '> /remind `target: @User` `time: 1 mon`   `message: What\'s up`\n'\
                '> /remind `target: @Role` `time: 24 dec`  `message: Merry Christmas`\n'\
                '> /remind `target: @everyone` `time: eoy` `message: Happy new year`\n'\
                '\n'\
                'create repeating reminders\n'\
                '> /remindme `time: every friday at 20:15` `message: do stuff`\n'\
                '> /remind `target: @User` `time: every year at 2nd july` `message: happy birthday`\n'\
                '\n'\
                'combine relative intervals\n'\
                '```1y 1mo 2 days -5h```'\
                '\n'\
                'try different formats\n'\
                '```'\
                '• 5 jul, 5th july, july 5\n'\
                '• 23 aug at 3pm, 23 aug at 15\n'\
                '• 2030\n'\
                '• tomorrow at 4pm\n'\
                '• every other week\n'\
                '• 2021-09-02T12:25:00+02:00\n'\
                '\n'\
                'Note: the parser uses day-first and year-least\n'\
                '      (01/02/03 -> 1st February 2003)\n'\
                'Note: specifying a timezone in iso-timestamps (e.g. +0200)\n'\
                '      will ignore the server timezone,\n'\
                '```'\
                '\n'\
                'use abbreviations for common terms\n'\
                '```'\
                '\t• eoy - remind at end of year\n'\
                '\t• eom - remind at end of month\n'\
                '\t• eow - remind at end of working week (Friday night)\n'\
                '\t• eod - remind at end of day\n'\
                '\t• y(ears)\n'\
                '\t• mo(nths)\n'\
                '\t• w(eeks)\n'\
                '\t• d(ays)\n'\
                '\t• h(ours)\n'\
                '\t• mi(ns)\n'\
                '```'\
                '\n'\
                'If you find a bug in the parser, please reach out to us and report it.'
                
    def __init__(self, client):
        self.client = client
    
    # =====================
    # helper methods
    # =====================
    
    async def send_feedback(self, ctx):
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
            feedback = await self.client.wait_for('message', check=msg_check, timeout=5*60)
        except asyncio.exceptions.TimeoutError:
            # abort the deletion
            await q.delete()
            await dm_test.edit(content='*Feedback Timeout*: You didn\'t enter your feedback fast enough.\nRe-invoke the command if you want to try again.') if dm_test else None
            return


        feedback_ch = self.client.get_channel(FEEDBACK_CHANNEL)

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


    async def send_help_page(self, ctx, page):
        
        page_list = ['overview', 'syntax', 'timezones']
        
        if page not in page_list:
            print('ERROR: unknown help page')
            await ctx.send(f'Error, unknown help page `{page}`')
            return
        
        def get_overview_eb():

            embed = discord.Embed(title='Remindme Help', description='Reminding you whenever you want')

            embed.add_field(name='/help [page]', value='directly access a specific help page', inline=False)
            embed.add_field(name='/timezone', value='set/get the timezone of this server', inline=False)
            embed.add_field(name='/remindme', value='reminding you after a set time period', inline=False)
            embed.add_field(name='/remind', value='remind another user after a set time period', inline=False)
            embed.add_field(name='/reminder_list', value='manage all reminders of this server', inline=False)


            embed.add_field(name='\u200b', 
                            inline=False,
                            value='If you like this bot, you can leave a vote at [top.gg](https://top.gg/bot/831142367397412874).\n'\
                                'If you find a bug contact us on [Github](https://github.com/Mayerch1/RemindmeBot) or join the support server.')

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

            eb = discord.Embed(title='Remindme Timezone Help', description='timezone help')

            eb.add_field(name='/timezone get', value='get the current timezone', inline=False)
            eb.add_field(name='/timezone set <string>', value='set a new timezone', inline=False)

            eb.add_field(name='\u200B', 
                        value='• Allowed timezones are any strings [defined by the IANA](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)\n'\
                            '• Some timezones are marked as \'deprecated\' but can be used with a warning\n'\
                            '• geo-referencing timezones (e.g. `Europe/Berlin`) should be preferred\n'\
                            '  over more general (and deprecated) timezones (e.g. `CET`)', inline=False)

            eb.add_field(name='\u200b', value='If you find a bug or want to give feedback, join the support server.', inline=False)

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

            eb = discord.Embed(title='Remindme Syntax Help', 
                            description=HelpModule.SYNTAX_HELP_PAGE)
            
            return eb

        def get_syntax_str():
            return '**Remindme Help** - parser syntax and example usage' + HelpModule.SYNTAX_HELP_PAGE


        def get_help_components(current_page='overview'):
            
            buttons = [
                manage_components.create_button(
                    style=ButtonStyle.URL,
                    label='Invite Me',
                    url='https://discord.com/oauth2/authorize?client_id=831142367397412874&permissions=84992&scope=bot%20applications.commands'
                ),
                manage_components.create_button(
                    style=ButtonStyle.URL,
                    label='Support Server',
                    url='https://discord.gg/Xpyb9DX3D6'
                ),
                manage_components.create_button(
                    style=ButtonStyle.gray,
                    label='Direct Feedback',
                    custom_id='help_direct_feedback'
                )
            ]
            row_1 = manage_components.create_actionrow(*buttons)
            
            
            options = [
                manage_components.create_select_option(
                    label='Overview Page',
                    description='List all available commands',
                    value='overview',
                    emoji='🌐',
                    default=(current_page=='overview')
                ),
                manage_components.create_select_option(
                    label='Syntax Page',
                    description='Show the reminder syntax, display examples',
                    value='syntax',
                    emoji='✏️',
                    default=(current_page=='syntax')
                ),
                manage_components.create_select_option(
                    label='Timezone Page',
                    description='Show timezone instructions',
                    value='timezones',
                    emoji='🕚',
                    default=(current_page=='timezones')
                ),
            ]
            help_selection = (
                manage_components.create_select(
                    custom_id='help_navigation',
                    placeholder='Please select a category',
                    min_values=1,
                    max_values=1,
                    options=options
                )
            )
            row_2 = manage_components.create_actionrow(help_selection)
            return [row_1, row_2]


        if page == 'overview':
            eb = get_overview_eb()
            fallback = get_overview_str()
            comps = get_help_components(page)
        elif page == 'syntax':
            eb = get_syntax_eb()
            fallback = get_syntax_str()
            comps = get_help_components(page)
        elif page == 'timezones':
            eb = get_timezone_eb()
            fallback = get_timezone_str()
            comps = get_help_components(page)

        
        if isinstance(ctx, ComponentContext):
            await ctx.edit_origin(embed=eb, components=comps)
        else:
            try:
                msg = await ctx.send(embed=eb, components=comps)
            except discord.errors.Forbidden:
                msg = await ctx.send(fallback)

        Analytics.help_page_called(page)
    
    # =====================
    # events functions
    # =====================
    
    
    @commands.Cog.listener()
    async def on_ready(self):
        print('HelpModule loaded')
        
        
    @commands.Cog.listener()
    async def on_component(self, ctx: ComponentContext):

        if ctx.custom_id == 'help_direct_feedback':
            await ctx.defer(edit_origin=True)
            await self.send_feedback(ctx)
        
        elif ctx.custom_id == 'help_navigation':
            sel_id = ctx.selected_options[0]
            await self.send_help_page(ctx, sel_id)
        
        
        
    # =====================
    # commands functions
    # =====================
    
    @cog_ext.cog_slash(name='help', description='Show the help page for this bot',
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
    async def get_help(self, ctx, page='overview'):
        await self.send_help_page(ctx, page)


def setup(client):
    client.add_cog(HelpModule(client))