import discord
import logging
from datetime import datetime, timedelta
from dateutil import tz

from lib.Connector import Connector

log = logging.getLogger('ext.help')


class HelpException(Exception):
    pass


class HelpElement:
    def __init__(self, cmd_name: str, description: str):
        self.cmd_name =  cmd_name
        self.help = description


class HelpPage:
    def __init__(self, name: str, title: str, emoji=None, description:str = None, short_description:str=None, elements:list[HelpElement] = [], override_footer:str = None):
        self.name=name
        self.title = title
        self.emoji = emoji
        self.description = description
        self.short_descr = short_description
        self.elements = elements
        self.override_footer = override_footer

    def to_embed(self, footer) -> discord.Embed:
        embed = discord.Embed(title=self.title, description=self.description)

        for el in self.elements:
            embed.add_field(name=el.cmd_name, value=el.help, inline=False)

        if footer or self.override_footer:
            embed.add_field(name='\u200b', inline=False, value=self.override_footer or footer)

        return embed

    def to_option(self, current_page=None) -> discord.SelectOption:
        return discord.SelectOption(
            label=f'{self.name.title()} Page',
            description=self.short_descr or self.name.title(),
            value=self.name,
            emoji=self.emoji,
            default=(self.name == current_page)
        )


class FeedbackModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        # override args
        kwargs['title'] = 'Direct Feedback'

        # pop custom args
        self.callback = kwargs['callback']
        del kwargs['callback']
        
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.InputText(
                label='Please enter your feedback for this bot',
                min_length=3,
                max_length=1500,
                style=discord.InputTextStyle.paragraph
            )
        )


class Help(discord.Cog):

    # redirect to modified/injected Cog scope
    cog_class: 'Help'
    is_cog_scope:bool =False

    # class variables only used in modified Cog
    # default Help-Class is not using these
    auto_detect = True
    default_page_name: str = None
    pages: dict[HelpPage] = {}
    feedback_ch = None
    feedback_mention = None
    permissions = discord.Permissions()
    support_url = None
    github_url = None
    tos_text = None
    privacy_text = None
    default_footer = None

    def __init__(self, client):
        self.client = client
        Help.is_cog_scope = True
    
    # =====================
    # config functions
    # =====================

    @staticmethod
    def init_help(client: discord.Bot, auto_detect_commands):
        """init internal variables used to hide PyCord complexity

           must be called *after* adding this class to extension
           but *before* the bot initializes the Cog (bot.run())
        Args:
            client (discord.Bot): discord Client/Bot
        """
        # pycord modifies the Help class scope when loading it as Cog
        # therefore, class attributes cannot directly be set/modified
        # (the id of the class changes -> class attrs are not shared)

        # the modified Cog-class can be retrieved by using the client
        # therefore it is saved into the unmodified class variables

        # the cog-modified class can be retrieved from the client
        # to hide this workaround from the user
        if 'discord.ext.help.help' not in client.extensions:
            raise HelpException('Help Cog not added to client. Use .load_extension(\'discord.ext.help.help\')')
        cog_class: Help = client.extensions['discord.ext.help.help'].Help
        Help.cog_class = cog_class
        Help.cog_class.auto_detect = auto_detect_commands


    def detect_commands(self):
        """automatically detect all available slash commands
           use their description as help description
           add the detected commands as new help page

           can only be called after init_help
           must be called after/in on_ready

        Args:
            client (discord.Bot): discord client/bot
        """
        if not Help.auto_detect:
            log.debug(f'skipping auto-detect')
            return

        cmds = self.client.all_commands
        log.debug(f'detected {len(cmds)} commands')

        elements = []
        for k in cmds:
            c = cmds[k]

            if not c.default_permission:
                # hide these commands (at least with the current permission system)
                continue

            if isinstance(c, discord.SlashCommandGroup):
                for sub_c in c.subcommands:
                    elements.append(
                        HelpElement(cmd_name=f'/{sub_c.qualified_name}', description=sub_c.description or '\u200b')
                    )    
            else:
                elements.append(
                    HelpElement(cmd_name=f'/{c.name}', description=c.description or '\u200b')
                )

        page = HelpPage(
            name='overview',
            title='Command Overview',
            description='List of all available commands',
            elements=elements,
            emoji='🌐'
        )
        Help.add_page(page, make_default=True)


    @staticmethod
    def add_page(page: HelpPage, make_default=False):
        if len(Help.pages) > 24:
            raise HelpException('Too many pages. A maximum of 25 pages is allowed')
        
        if len(page.title) > 256:
            raise HelpException('Page title too long, must be smaller eqauls to 256 chars')
        if len(page.description) > 4096:
            raise HelpException('Page description too long, must be smaller eqauls to 4096 chars')
        if len(page.elements) > 24:
            # discord can have 25 fields, but one is used for custom footer
            raise HelpElement('Too many page elements. Max. 24 elements are supported')
        
        # field constraints are not checked for now
        # an error will occur at runtime, if exceeded

        if Help.is_cog_scope:
            pages = Help.pages
        else:
            pages = Help.cog_class.pages

        pages[page.name] = page
        if len(pages) == 1 or make_default:
            if Help.is_cog_scope:
                Help.default_page_name = page.name
            else:
                Help.cog_class.default_page_name = page.name

        log.debug(f'added new help page with {len(page.elements)} elements')


    @staticmethod
    def set_feedback(channel_id: int, role_id: int):
        if Help.is_cog_scope:
            Help.feedback_ch = channel_id
            Help.feedback_mention = role_id
        else:
            Help.cog_class.feedback_ch = channel_id
            Help.cog_class.feedback_mention = role_id
        
        log.debug(f'set direct feedback to {channel_id}/{role_id}')


    @staticmethod
    def invite_permissions(permissions: discord.Permissions):
        if Help.is_cog_scope:
            Help.permissions = permissions
        else:
            Help.cog_class.permissions = permissions
        log.debug(f'set invite permissions to {permissions.value}')


    @staticmethod
    def support_invite(link: str):
        if Help.is_cog_scope:
            Help.support_url = link
        else:
            Help.cog_class.support_url = link
        log.debug(f'set support link to {link}')


    @staticmethod
    def set_tos_text(text: str):
        if Help.is_cog_scope:
            Help.tos_text = text
        else:
            Help.cog_class.tos_text = text
        log.debug(f'updated tos text')


    @staticmethod
    def set_privacy_text(text: str):
        if Help.is_cog_scope:
            Help.privacy_text = text
        else:
            Help.cog_class.privacy_text = text
        log.debug(f'updated privacy text')


    @staticmethod
    def set_tos_file(file: str):
        text = open(file).read()
        Help.set_tos_text(text)


    @staticmethod
    def set_privacy_file(file: str):
        text = open(file).read()
        Help.set_privacy_text(text)


    @staticmethod
    def set_default_footer(default_footer:str):
        if Help.is_cog_scope:
            Help.default_footer = default_footer
        else:
            Help.cog_class.default_footer = default_footer


    @staticmethod
    def set_github_url(github_url:str):
        if Help.is_cog_scope:
            Help.github_url = github_url
        else:
            Help.cog_class.github_url = github_url


    # =====================
    # help stuff
    # =====================

    async def help_send_tos(self, interaction: discord.Interaction):
        await interaction.response.send_message(Help.tos_text or '*Missing Content*', ephemeral=True)
        

    async def help_send_privacy(self, interaction: discord.Interaction):
        await interaction.response.send_message(Help.privacy_text or '*Missing Content*', ephemeral=True)


    async def send_feedback(self, interaction: discord.Interaction):
        feedback = FeedbackModal(callback=self.process_feedback)
        await interaction.response.send_modal(feedback)


    async def process_feedback(self, interaction: discord.Interaction):
        def _error_components():
            view = discord.ui.View(timeout=None)
            
            buttons = []

            if Help.support_url:
                buttons.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label='Support Server',
                        url=Help.support_url
                    )
                )

            if Help.github_url:
                buttons.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label='Github Issue',
                        url=f'{Help.github_url}/issues'
                    )
                )

            if buttons:
                for b in buttons:
                    view.add_item(b)
                return view
            else:
                return None

        def _error_text():
            return 'There was an issue while saving your feedback.\n'\
                'Please report this bug on the *support server* or on *GitHub*'

        async def send_error(interaction: discord.Interaction):
            error_view = _error_components()
            if error_view:
                await interaction.response.send_message(content=_error_text(), view=error_view, ephemeral=True)
            else:
                await interaction.response.send_message(content=_error_text(), ephemeral=True)

        try:
            ch = await self.client.fetch_channel(Help.feedback_ch)
        except (discord.errors.Forbidden, discord.errors.NotFound) as ex:
            await send_error(interaction)
            log.error('failed to fetch feedback channel', exc_info=ex)
            raise ex

        feedback = interaction.data['components'][0]['components'][0]['value']
        feedback_str = f'<@&{Help.feedback_mention}> New Feedback:\n'
        feedback_str += f'Author: {interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})\n\n'

        content = feedback.replace('\n', '\n> ') # make sure multiline doesn't break quote style
        feedback_str += f'> {content}\n'

        try:
            await ch.send(feedback_str)
        except discord.errors.Forbidden as ex:
            await send_error(interaction)
            log.error('failed to send message into feedback channel', exc_info=ex)
            raise ex

        await interaction.response.send_message('Thanks for giving feedback to improve the bot', ephemeral=True)


    async def send_help_page(self, ctx: discord.ApplicationContext, page: str='overview'):
        
        if page not in Help.pages:
            log.error(f'unknown help page {page}')
            await ctx.response.send_message(f'Error, unknown help page `{page}`', ephemeral=True)
            return
        

        def get_help_view(current_page=None):

            view = discord.ui.View(timeout=0.001)
            components = []

            # === ROW 0 ===
            if Help.permissions is not None:
                components.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label='Invite Me',
                        url=f'https://discord.com/api/oauth2/authorize?client_id={self.client.user.id}&permissions={Help.permissions.value}&scope=bot%20applications.commands',
                        row=0
                    )
                )
            if  Help.support_url:
                components.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label='Support Server',
                        url=Help.support_url,
                        row=0
                    )
                )
            if Help.feedback_ch:
                components.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.secondary,
                        label='Direct Feedback',
                        custom_id='help_direct_feedback',
                        row=0
                    )
                )

            components.append(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label='Self-Test',
                    custom_id='help_test_function',
                    row=0
                )
            )

            # === ROW 1 ===
            if Help.tos_text:
                components.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.secondary,
                        label='ToS',
                        custom_id='help_tos',
                        row=1
                    )
                )
            if Help.privacy_text:
                components.append(
                    discord.ui.Button(
                        style=discord.ButtonStyle.secondary,
                        label='Privacy',
                        custom_id='help_privacy',
                        row=1
                    )
                )

            # === ROW 3 ===
            if len(Help.pages) > 1:
                options = [Help.pages[k].to_option(current_page) for k in Help.pages]
                components.append(discord.ui.Select(
                        options=options,
                        placeholder='Please select a category',
                        min_values=1,
                        max_values=1,
                        row=3,
                        custom_id='help_navigation'
                    )
                )
            for c in components:
                view.add_item(c)

            return view


        page = Help.pages[page]

        embed = page.to_embed(Help.default_footer)
        view = get_help_view(page.name)

        # permissions are always guaranteed
        if isinstance(ctx, discord.ApplicationContext):
            # this is a reaction to a command
            await ctx.respond(embeds=[embed], view=view)
        elif isinstance(ctx, discord.Interaction):
            # button/select menu
            await ctx.response.edit_message(embeds=[embed], view=view)



    async def send_test_messages(self, ctx: discord.Interaction):
        
        instance_id = ctx.guild.id if ctx.guild else ctx.author.id
        experimental = Connector.is_experimental(instance_id)
        legacy = Connector.is_legacy_interval(instance_id)
        
        # create a report of the setup
        can_embed = False
        can_text = False
        can_dm = False
        ping = int(self.client.latency*1000)

        created_at = discord.utils.snowflake_time(ctx.id)

        response_time = (datetime.utcnow().replace(tzinfo=tz.UTC)-created_at)
        response_ms = int(response_time.total_seconds()*1000)
        
        # try-catch is the easiest approach for this problem
        # instead of checking all permission overwrites
        eb = discord.Embed(title='Test Message', 
                           description='You can safely delete this message')
        try:
            await ctx.channel.send(embed=eb)
        except discord.Forbidden:
            # failure might still grant text_permission
            text = 'Test Message, *please ignore this*'
            try:
                await ctx.channel.send(text)
            except discord.Forbidden:
                pass  # failure grants no permission
            else:
                can_text = True
        else:
            can_embed = can_text = True
            
            
        # other critical parameters are the correct timezone
        # aswell as the ability to DM the user
        tz_str = Connector.get_timezone(instance_id)
        local_time = datetime.now(tz.gettz(tz_str)).strftime('%H:%M')
        
        dm = await ctx.user.create_dm()
        try:
            await dm.send('Self-testing... *please ignore this.*')
        except discord.Forbidden:
            pass  # no permission on failure
        else:
            can_dm = True
        
        
        # create the text snippets used to inform
        # the user
        color=0x96eb67
        
        if can_embed:
            delivery_result = 'OK'
            delivery_hint = ''
        elif can_text:
            delivery_result = '*Text Only*'
            delivery_hint = '• Enable `Embed Links` permissions, to allow for a better reminder display\n'
            color = 0xcceb67
        else:
            delivery_result = '**Failed**'
            delivery_hint = '• Enable `Send Message` permissions for this text channel\n'
            color = 0xde4b55  # red-ish

        if can_dm:
            dm_result = 'OK'
            dm_hint = ''
        else:
            dm_result = '**Failed**'
            dm_hint = '• Allow me to send you DMs to configure reminders and to receive error information, '\
                        '[change your preferences]({:s}) and test again.'.format(r'https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-')
            if can_embed:
                # do not overwrite the color of more severe errors
                color = 0xcceb67
        
        
        eb = discord.Embed(title='Self-Test',
                           description=delivery_hint + '\n' + dm_hint)
        eb.color = color
        
        eb.add_field(name='Reminder delivery', value=delivery_result)
        eb.add_field(name='DM permissions', value=dm_result)
        
        eb.add_field(name='Local Time', value=f'{local_time} (based on timezone settings)', inline=False)


        eb.add_field(name='Legacy mode', value=legacy, inline=True)
        eb.add_field(name='Experimental mode', value=experimental, inline=True)    
        eb.add_field(name='\u200b', value='\u200b', inline=True)


        eb.add_field(name='Discord API Latency', value=f'{ping} ms', inline=True)
        eb.add_field(name='Library Latency*', value=f'{response_ms} ms', inline=True)


        test_time = (datetime.utcnow().replace(tzinfo=tz.UTC)-created_at)
        test_ms = int(test_time.total_seconds()*1000)
        eb.add_field(name='Self-Test Duration*', value=f'{test_ms} ms', inline=False)

        eb.set_footer(text='*this includes server and discord time inaccuracies towards `Coordinated Universal Time`')

        
        await ctx.response.send_message(embed=eb, ephemeral=True)


    # =====================
    # command functions
    # =====================
    @discord.slash_command(name='help', description='Show the help page for this bot')
    async def help(self, ctx: discord.ApplicationContext):
        await self.send_help_page(ctx, page=Help.default_page_name)

    # =====================
    # events functions
    # =====================

    @discord.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if 'custom_id' not in interaction.data:
            # we only care about buttons/selects here
            return

        custom_id = interaction.data['custom_id']

        if custom_id == 'help_tos':
            await self.help_send_tos(interaction)
        elif custom_id == 'help_privacy':
            await self.help_send_privacy(interaction)
        elif custom_id == 'help_direct_feedback':
            await self.send_feedback(interaction)
        elif custom_id == 'help_navigation':
            page = interaction.data['values'][0] # min select is 1
            await self.send_help_page(interaction, page)
        elif custom_id == 'help_test_function':
            await self.send_test_messages(interaction)


    @discord.Cog.listener()
    async def on_ready(self):
        log.info('HelpModule loaded')
        self.detect_commands()


def setup(client):
    client.add_cog(Help(client))