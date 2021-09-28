import asyncio
import re

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

from lib.Connector import Connector
from lib.Analytics import Analytics, Types
from lib.CommunitySettings import CommunitySettings, CommunityAction

def _disable_components(navigation_row):
    for comp in navigation_row['components']:
        comp['disabled'] = True


async def wait_confirm_deny(client, message: discord.Message, timeout, author):
    """Use components to ask user for confirm/denial of a message.
       Can return True/False/None

    Args:
        client ([type]): bot client
        message (discord.Message): message to append components to
        timeout ([type]): timeout in seconds, until None is returned
        author ([type]): user which is allowed to react

    Return:
        true if user accepts,
        false if user denies,
        None on timeout

    """

    def check(ctx: ComponentContext):
        return ctx.author_id == author.id

    buttons = [
        manage_components.create_button(
            style=ButtonStyle.danger,
            label='Deny',
            custom_id='interaction_condeny_deny'
        ),
        manage_components.create_button(
            style=ButtonStyle.success,
            label='Confirm',
            custom_id='interaction_condeny_accept'
        )
    ]
    navigation_row = manage_components.create_actionrow(*buttons)
    await message.edit(components=[navigation_row])

    success_ack = False
    while not success_ack:
        try:
            r_ctx = await manage_components.wait_for_component(client, components=[navigation_row], timeout=timeout, check=check)
        except asyncio.exceptions.TimeoutError:
            _disable_components(navigation_row)
            await message.edit(components=[navigation_row])
            return None

        try:
            await r_ctx.defer(edit_origin=True)
        except discord.NotFound:
            success_ack = False
        else:
            success_ack = True

    if r_ctx.custom_id == 'interaction_condeny_accept':
        result = True
    else:
        result = False

    await message.edit(components=[])
    return result



async def get_client_response(client, message: discord.Message, timeout, author, validation_fnc=None, silent_error=False):
    """Wait for user input into channel of message
       waits until a message is received which fullfills validation_fnc

    Args:
        client ([type]): bot client
        message (discord.Message): only channel of this message is allowed
        timeout ([type]): timeout before None is returned
        author ([type]): author of message
        validation_fnc ([type], optional): function only returns when this is fullfilled (or timeout). Defaults to None
    """
    def check(m):
        return m.channel.id == message.channel.id and m.author == author


    answer_accepted = False
    while not answer_accepted:
        try:
            reaction = await client.wait_for('message', check=check, timeout=timeout)
        except asyncio.exceptions.TimeoutError:
            await message.add_reaction('⏲') # timer clock
            return None
        else:
            # check against validation_fnc, if given
            answer = reaction.content
            if validation_fnc is not None:
                answer_accepted = validation_fnc(answer)
                if not answer_accepted and not silent_error:
                    await message.channel.send('Invalid format, try again')
            else: 
                answer_accepted = True

    return answer


async def _show_ack(client, messageable, title, description, timeout, edit_origin, color, btn_style, embed_override=None, hidden=False):

    if not embed_override:
        eb = discord.Embed(title=title, description=description, color=color)
    else:
        eb = embed_override
    
    buttons = [
        manage_components.create_button(
            style=btn_style,
            label='Acknowledge',
            custom_id='reminder_stm_generic_ack'
        )
    ]
    action_row = manage_components.create_actionrow(*buttons)
    
    if edit_origin:
        await messageable.edit_origin(embed=eb, components=[action_row])
    elif hidden:
        await messageable.send(embed=eb, components=[action_row], hidden=True)
    else:
        await messageable.send(embed=eb, components=[action_row])


    success_ack = False

    while not success_ack:
        try:
            ack_ctx = await manage_components.wait_for_component(client, components=action_row, timeout=timeout)
        except asyncio.exceptions.TimeoutError:
            return None

        try:
            await ack_ctx.defer(edit_origin=True)
        except discord.NotFound:
            success_ack = False
        else:
            success_ack = True
        
        
    return ack_ctx

async def show_success_ack(client, messageable, title, description, timeout=5*60, edit_origin=False):
    """show an success embed to the user and wait for ack button press
        if user doesn't react within timeout, None is returned
        
        tries again, if interaction times out

    Args:
        messageable (ctx or channel): Target to send the embed to
        title ([type]): [description]
        description ([type]): [description]
        timeout ([type], optional): [description]. Defaults to 5*60.
        edit_origin (bool): use .edit_origin to send message, throws exception if True and messageable is not a context.

    Returns:
        ComponentContext: reaction context already in deferred state, None on timeout
    """
    color = 0x409fe2
    btn_style = ButtonStyle.green
    return await _show_ack(client, messageable, title, description, timeout, edit_origin, color, btn_style)


async def show_error_ack(client, messageable, title, description, timeout=5*60, edit_origin=False):
    """show an error embed to the user and wait for ack button press
        if user doesn't react within timeout, None is returned
        
        tries again, if interaction times out

    Args:
        messageable (ctx or channel): Target to send the embed to
        title ([type]): [description]
        description ([type]): [description]
        timeout ([type], optional): [description]. Defaults to 5*60.
        edit_origin (bool): use .edit_origin to send message, throws exception if True and messageable is not a context.

    Returns:
        ComponentContext: reaction context already in deferred state, None on timeout
    """
    color = 0xff0000
    btn_style = ButtonStyle.red
    return await _show_ack(client, messageable, title, description, timeout, edit_origin, color, btn_style)



async def check_user_permission(ctx, required_perms:CommunitySettings=None, hidden:bool=True):
    """performs check on if user has sufficient permission to excute the command
       the user has permission if the server is not a community server
       
       otherwise the community mode is checked to make sure if user needs permission
       depending on moderator mode of user, permission might be granted or not
       
       if not invoked on a server, permission is always granted
       
       on no permission, an error embed will be shown
       this will respond to the handed ctx
       
       if permission is present, ctx will not be responded to

    Args:
        ctx (Slash/Command Context): context of the interaction
        required_perms (CommunityAction, default None): the demanded permissions for this command
        hidden (bool, default True): set how to respond to the ctx in case of missing permissions

    Returns:
        bool: True if user has permission, False if not and ctx was responded 
    """
    if not ctx.guild:
        return True

    g_id = ctx.guild.id
    author = ctx.author
    
    return await check_user_permission_raw(None, ctx, g_id, author.roles, required_perms=required_perms, hidden=hidden)
    

async def check_user_permission_raw(client, messeagable, guild_id: int, user_roles: [], required_perms:CommunitySettings=None, wait_ack=False, hidden:bool=True):
    """performs check on if user has sufficient permission to excute the command
       the user has permission if the server is not a community server
       
       otherwise the community mode is checked to make sure if user needs permission
       depending on moderator mode of user, permission might be granted or not
       
       if not invoked on a server, permission is always granted
       
       on no permission, an error embed will be shown
       this will respond to the handed ctx
       
       if permission is present, ctx will not be responded to

    Args:
        client (discord.Client): Required if wait_ack is True, if None: wait_ack is ignored
        messeagable (Messeagable Type): used to respond in case of error
        guild_id (int): id of guild in question
        user_roles (list): list of roles or list of role ids
        required_perms (CommunitySettings, optional): the required permission for the action. Defaults to None.
        wait_ack (bool): in case of failure, do not return until user ACKs the error message
        hidden (bool, optional): post error message hidden. Defaults to True.
    """
    
    def get_error_embed(required_perms, settings):
        
        if (settings.mods_only):
            missing_perms = 'The bot is set to moderator-only mode\n'
        else:
            missing_perms = 'You do not have permissions to\n'
            if (required_perms.repeating and settings.restrict_repeating):
                missing_perms += '• Repeating Reminders\n'
            if (required_perms.everyone and settings.restrict_everyone):
                missing_perms += '• Mention Everyone\n'
            if (required_perms.foreign and settings.restrict_foreign):
                missing_perms += '• Remind other users\n'
            if required_perms.settings:
                missing_perms += '• Change Bot Settings\n'
            
        
        eb = discord.Embed(title='Missing Permissions',
                           description=f'{missing_perms}'\
                                        '\n'\
                                        'If you think you should be able to perform this command,\n'\
                                        'ask an admin to edit the moderator roles or change the community mode.\n'\
                                        '\n'\
                                        'This can be done with `/settings menu`')
        eb.color = 0xff0000
        return eb

    # if comm mode is disabled, all settings/mods are ignored
    community_mode = Connector.get_community_mode(guild_id)
    if community_mode == Connector.CommunityMode.DISABLED:
        return True
    
    # moderators can do everything
    is_mod = Connector.is_moderator(user_roles)
    if is_mod:
        return True
    
    if required_perms is None:
        required_perms = CommunityAction() # relaxed permissions, assume no permissions required
    settings = Connector.get_community_settings(guild_id)
    
    # at this point the user has no mod permissions
    if settings.mods_only or\
        (required_perms.repeating and settings.restrict_repeating) or\
        (required_perms.everyone and settings.restrict_everyone) or\
        (required_perms.foreign and settings.restrict_foreign) or\
        (required_perms.settings):
            
        err_embed = get_error_embed(required_perms, settings)

        if client and wait_ack:
            await _show_ack(client=client, 
                            messeagable=messeagable, 
                            title=None, 
                            description=None, 
                            timeout=5*60, 
                            edit_origin=False, 
                            color=0xff0000, 
                            btn_style=ButtonStyle.red,
                            embed_override=err_embed, 
                            hidden=hidden)
        else:    
            if isinstance(messeagable, SlashContext):
                await messeagable.send(embed=err_embed, hidden=hidden)
            else:
                await messeagable.send(embed=err_embed)

        Analytics.command_denied()
        
        return False
    else:
        return True