import asyncio
from datetime import datetime, timedelta
import re
from typing import Union

import discord

from lib.Connector import Connector, Reminder
from lib.Analytics import Analytics, Types
from lib.CommunitySettings import CommunitySettings, CommunityAction

import logging

log = logging.getLogger('Remindme')


class CustomView(discord.ui.View):
    def __init__(self, message=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.value = None
        self.message: Union[discord.Message, discord.Interaction, discord.WebhookMessage] = message

    def disable_all(self):
        """disable all components in this view
           and stop the view
        """

        # self.disable_all_items()
        for child in self.children:
           # make all button childs gray
           if isinstance(child, discord.ui.Button):
               child.style = discord.ButtonStyle.secondary
           child.disabled = True


    async def on_timeout(self):
        self.disable_all()

        if self.message:
            if hasattr(self.message, 'edit_original_message'):
                await self.message.edit_original_message(view=self)
            else:
                log.debug('on_timeout: message has no attr "edit_original_message. Do not disable btn elements"')

    async def transfer_to_message(self, new_msg, override_old):
        """attach this view context to a new message
           all components of the old message will be deleted by edit

           the content can optionally be replaced with "See below"

        Args:
            new_msg (_type_): _description_
            override_old (_type_): _description_
        """
        
        if isinstance(self.message, discord.WebhookMessage):
            func = self.message.edit
        else:
            func = self.message.edit_original_message

        if self.message:
            if override_old:
                await func(content='Please see the Message below', embed=None, view=None)
            else:
                await func(view=None)
                

        self.message = new_msg




class AckView(CustomView):
    def __init__(self, dangerous_action=False, message=None, *args, **kwargs):
        super().__init__(message=message, *args, **kwargs)
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


class UndeliveredView(CustomView):
    def __init__(self, reminder_id, *args, **kwargs):
        super().__init__(*args , **kwargs)
        self.r_id = reminder_id


    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):

        # modify button colors
        if not Connector.delete_reminder(self.r_id):
            Connector.delete_interval(self.r_id)

        self.disable_all()
        await interaction.response.edit_message(view=self)

        self.value = False
        self.stop()


class SnoozeView(CustomView):
    def __init__(self, reminder: Reminder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reminder = reminder
        self.r_id = reminder._id


    async def snooze_reminder(self, button: discord.ui.Button, interaction: discord.Interaction, delay_seconds: int):
        
        # convert to json and back to reminder object
        # this automatically converts intervals to reminders
        snoozed = Reminder(self.reminder._to_json())

        snoozed._id = None
        snoozed.created_at = datetime.utcnow()
        snoozed.msg = (snoozed.msg+' (snoozed)')[:25]
        snoozed.at = self.reminder.at + timedelta(seconds=delay_seconds)

        Connector.add_reminder(snoozed)

        self.disable_all()
        button.style = discord.ButtonStyle.green

        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label='+15m', emoji='⏱️', style=discord.ButtonStyle.blurple)
    async def snooze_15(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.snooze_reminder(button, interaction, 15*60)

    @discord.ui.button(label='+60m', emoji='⏱️', style=discord.ButtonStyle.blurple)
    async def snooze_60(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.snooze_reminder(button, interaction, 60*60)

    

class SnoozeIntervalView(SnoozeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def delete(self, button: discord.ui.Button, interaction: discord.Interaction):

        if interaction.user.id != self.reminder.author:
            await interaction.response.send_message('You do not have permissions to delete this reminder', ephemeral=True)
            return

        Connector.delete_interval(self.r_id)
        self.disable_all()
        button.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(view=self, embed=discord.Embed(title='Deleted Reminder', description='The reminder was deleted by its author', color=0x409fe2)) # cyan blue
        self.stop()


    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.danger)
    async def del_reminder(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.delete(button, interaction)