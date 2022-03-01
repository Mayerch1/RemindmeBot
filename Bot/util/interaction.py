import asyncio
import re
from typing import Union

import discord

from lib.Connector import Connector
from lib.Analytics import Analytics, Types
from lib.CommunitySettings import CommunitySettings, CommunityAction



class CustomView(discord.ui.View):
    def __init__(self, message=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.value = None
        self.message: Union[discord.Message, discord.Interaction] = message

    def disable_all(self):
        """disable all components in this view
           and stop the view
        """
        for child in self.children:
            # make all button childs gray
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.secondary
            child.disabled = True


    async def on_timeout(self):
        self.disable_all()

        if self.message:
            await self.message.edit_original_message(view=self)

    async def transfer_to_message(self, new_msg, override_old):
        """attach this view context to a new message
           all components of the old message will be deleted by edit

           the content can optionally be replaced with "See below"

        Args:
            new_msg (_type_): _description_
            override_old (_type_): _description_
        """
        
        if self.message:
            if override_old:
                await self.message.edit_original_message(content='Please see the Message below', embed=None, view=None)
            else:
                await self.message.edit_original_message(view=None)

        self.message = new_msg




class AckView(CustomView):
    def __init__(self, dangerous_action=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.danger = dangerous_action
        if dangerous_action:
            self.ack.style = discord.ButtonStyle.danger

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.success)
    async def ack(self, button:  discord.ui.Button, interaction: discord.Interaction):

        # but remove the other button this time
        self.disable_all()
        button.label = 'Confirmed'
        button.style = discord.ButtonStyle.red if self.danger else discord.ButtonStyle.green
        self.children = [button]

        await interaction.response.edit_message(view=self)

        self.value = True
        self.stop()



class ConfirmDenyView(AckView):
    def __init__(self, dangerous_action=False, *args, **kwargs):
        super().__init__(dangerous_action, *args , **kwargs)

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="Abort", style=discord.ButtonStyle.grey)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        # modify button colors
        self.disable_all()
        button.label='Aborted'
        button.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(view=self)

        self.value = False
        self.stop()




class MulitDropdownView(CustomView):
    def __init__(self, dropdowns: list[discord.ui.Select], *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Adds the dropdown to our view object.
        for drop in dropdowns:
            drop.callback = self.callback
            self.add_item(drop)

    
    async def callback(self, interaction: discord.Interaction):
        
        # min select 1 guaranteed
        self.value = interaction.data['values'][0]

        # find selected item and make it default
        # this is a workaround as disabling the item 
        # resets the user selection
        self.disable_all()
        child = [x for x in self.children if x.custom_id == interaction.data['custom_id']][0]
        opt = [x for x in child.options if x.value==self.value][0]
        
        await interaction.response.edit_message(view=self)
        # go ahead and disable the view
        opt.default = True
        self.stop()




# async def get_client_response(client, message: discord.Message, timeout, author, validation_fnc=None, silent_error=False):
#     """Wait for user input into channel of message
#        waits until a message is received which fullfills validation_fnc

#     Args:
#         client ([type]): bot client
#         message (discord.Message): only channel of this message is allowed
#         timeout ([type]): timeout before None is returned
#         author ([type]): author of message
#         validation_fnc ([type], optional): function only returns when this is fullfilled (or timeout). Defaults to None
#     """
#     def check(m):
#         return m.channel.id == message.channel.id and m.author == author


#     answer_accepted = False
#     while not answer_accepted:
#         try:
#             reaction = await client.wait_for('message', check=check, timeout=timeout)
#         except asyncio.exceptions.TimeoutError:
#             await message.add_reaction('⏲') # timer clock
#             return None
#         else:
#             # check against validation_fnc, if given
#             answer = reaction.content
#             if validation_fnc is not None:
#                 answer_accepted = validation_fnc(answer)
#                 if not answer_accepted and not silent_error:
#                     await message.channel.send('Invalid format, try again')
#             else: 
#                 answer_accepted = True

#     return answer
