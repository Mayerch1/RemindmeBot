import discord
from discord.ext import commands, tasks

from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle

import dateutil.rrule as rr

from lib import Reminder



async def ask_count_value(client, stm, reminder):

    eb = discord.Embed(title='Interval settings',
                      description='Enter the amount of repetitions for this event')

    await stm.menu_msg.edit(embed=eb)


    def msg_check(msg):
        return msg.channel.id == stm.dm.id and\
                msg.author.id == stm.scope.user_id

    count = None
    while True:
        message = await client.wait_for('message', check=msg_check)

        try:
            count = int(message.content)
        except ValueError:
            await stm.dm.send('You need to enter an integer number')
            continue
        else:
            return count

        # show when reminder is going to expire

    return count


async def ask_until_date(client, stm, reminder):
    count = 5
    return count



async def ical_repeating_interval(client, stm, reminder, freq):
    
    wkst = rr.MO

    repeat_opts = [
        manage_components.create_select_option(
            label='Endless',
            description='the reminder will never end to be repeated',
            value='endless'
        ),
        manage_components.create_select_option(
            label='Count',
            description='Set how often the reminder is repeated',
            value='count'
        )#,
        #manage_components.create_select_option(
        #    label='Until',
        #    description='Repeat the reminder until the given date',
        #    value='until'
        #)
    ]
    repeat_selection = (
        manage_components.create_select(
                custom_id='reminder_list_repeat_stop',
                placeholder='Select a stopping condition',
                min_values=1,
                max_values=1,
                options=repeat_opts
            )
    )
    row = manage_components.create_actionrow(repeat_selection)

    eb = discord.Embed(title='Interval settings',
                      description='Select when the repetition should stop')
    await stm.menu_msg.edit(embed=eb, components=[row])

    end_ctx = await manage_components.wait_for_component(client, components=[repeat_selection])
    e_opt = end_ctx.selected_options[0]

    if e_opt == 'until':
        count = await ask_until_date(client, stm, reminder)
    elif e_opt == 'count':
        count = await ask_count_value(client, stm, reminder)
    else:
        # endless
        count = None

    print(count)




async def interactive_menu(client, stm, reminder):

    
    repeat_opts = [
        manage_components.create_select_option(
            label='Never',
            value='never'
        ),
        manage_components.create_select_option(
            label='Daily',
            value='daily'
        ),
        manage_components.create_select_option(
            label='Weekly',
            value='weekly'
        ),
        manage_components.create_select_option(
            label='Monthly',
            value='monthly'
        ),
        manage_components.create_select_option(
            label='Yearly',
            value='yearly'
        )
    ]
    repeat_selection = (
        manage_components.create_select(
                custom_id='reminder_list_repeat_type',
                placeholder='Select a repeating pattern',
                min_values=1,
                max_values=1,
                options=repeat_opts
            )
    )
    row = manage_components.create_actionrow(repeat_selection)

    eb = discord.Embed(title='Interval settings',
                      description='Select the pattern at which you want to repeat the reminder')
    await stm.menu_msg.edit(embed=eb, components=[row])

    repeat_ctx = await manage_components.wait_for_component(client, components=[repeat_selection])
    c_opt = repeat_ctx.selected_options[0]

    await repeat_ctx.defer(edit_origin=True)


    if c_opt == 'never':
        # TODO: clear
        pass
    else:
        # maybe add hourly, minutely
        # later as premium feature?
        if c_opt == 'daily':
            freq = rr.DAILY
        elif c_opt == 'weekly':
            freq = rr.WEEKLY
        elif c_opt == 'monthly':
            freq = rr.MONTHLY
        elif c_opt == 'yearly':
            freq = rr.YEARLY
        else:
            print(f'ERROR: unknown repeat mode {c_opt}')
            return None
        await ical_repeating_interval(client, stm, reminder, freq)


    # the selected interval must be converted into 
    # a universal format
    # then the reminder is converted into a repeating 
    # reminder

    print('x')