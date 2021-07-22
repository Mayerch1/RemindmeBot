import asyncio
import re

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle


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

    try:
        r_ctx = await manage_components.wait_for_component(client, components=[navigation_row], timeout=timeout, check=check)
    except asyncio.exceptions.TimeoutError:
        _disable_components(navigation_row)
        await message.edit(components=[navigation_row])
        return None

    await r_ctx.defer(edit_origin=True)

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

