import discord
from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz

import util.interaction
import lib.input_parser
import lib.ReminderRepeater
from lib.Reminder import Reminder, IntervalReminder
from lib.Connector import Connector
from lib.Analytics import Analytics, Types


class RuleMode(Enum):
    RRULE_ADD=0
    RRULE_EX_ADD=1
    DATE_ADD=2
    DATE_EX_ADD=3


class RuleModal(discord.ui.Modal):
    def __init__(self, field, custom_callback, mode: RuleMode, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = None
        self.custom_callback = custom_callback
        self.message = None
        self.mode = mode


        self.add_item(
            discord.ui.InputText(
                label=field,
                style=discord.InputTextStyle.singleline
            )
        )


    async def callback(self, interaction: discord.Interaction):
        user_input = self.children[0].value
        self.value = user_input

        
        if self.custom_callback:
            await self.custom_callback(interaction, self.value, self.mode)
        else:
            await interaction.response.send_message('OK', ephemeral=True)


class ReminderIntervalModifyView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)

        self.reminder = reminder
        self.stm = stm

    def get_embed(self) -> discord.Embed:
        return discord.Embed()



class ReminderIntervalAddView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)

        self.reminder = reminder
        self.stm = stm
        self.update_btn_activation()

    def get_embed(self) -> discord.Embed:
        return discord.Embed(
            title='Add new rules',
            description='Specify which type of rule you want to add to this reminder.\n'\
                        'You can use an [RRULE Generator](https://www.textmagic.com/free-tools/rrule-generator)'
        )

    def update_btn_activation(self):
        """disable rule buttons if too many rules are present
        """
        if isinstance(self.reminder, IntervalReminder):
            if len(self.reminder.get_rule_dicts()) >= 25:
                disabled=True
            else:
                disabled=False
        else:
            disabled=False

        for btn in self.children:
            btn.disabled=disabled

        self.return_btn.disabled=False # always allow return
        


    async def rrule_callback(self, interaction: discord.Interaction, user_input: str, mode: RuleMode):

        action_str = 'Rrule' if mode==RuleMode.RRULE_ADD else 'Rrule exception'
        action_modifier = '*not*' if mode==RuleMode.RRULE_EX_ADD else ''
     
        dtstart = self.reminder.first_at if isinstance(self.reminder, IntervalReminder) else self.reminder.at

        rrule_input = user_input.lower()
        rrule, error = lib.input_parser.rrule_normalize(rrule_input, dtstart, self.stm.scope.instance_id)

        # transfer 
        msg = None

        if not rrule:
            if error:
                error_str = error
            else: 
                error_str = 'Unknown error occurred while parsing the rrule.'

            embed = discord.Embed(title='Invalid rrule',
                                  color=0xff0000,
                                  description=error_str+'\nPlease try again.')
            view = util.interaction.AckView()
            msg = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await self.transfer_to_message(msg, override_old=True) # after sending the new message, as msg is required

            await view.wait()

        else:
            # success
            eb = discord.Embed(title=f'New {action_str}',
                           description='Add the rule `{:s}`?. The reminder is {:s} triggered according to this rule.'\
                                        .format(str(rrule), action_modifier))
            view = util.interaction.ConfirmDenyView(dangerous_action=False)

            msg = await interaction.response.send_message(embed=eb, view=view, ephemeral=True)
            await self.transfer_to_message(msg, override_old=True) # after sending the new message, as msg is required

            await view.wait()

            if view.value:
                # store to db
                if mode == RuleMode.RRULE_ADD:
                    self.reminder = lib.ReminderRepeater.add_rules(self.reminder, rrule=str(rrule))
                else:
                    self.reminder = lib.ReminderRepeater.add_rules(self.reminder, exrule=str(rrule))

          
        # return to normal view in any case
        eb = self.get_embed()
        self.update_btn_activation() # update in case too many rules are present
        msg = await self.message.edit_original_message(embed=eb, view=self)


    async def date_callback(self, interaction: discord.Interaction, user_input: str, mode: RuleMode):

        action_str = 'single date' if mode==RuleMode.DATE_ADD else 'date exception'

        utcnow = datetime.utcnow()
        date, info = lib.input_parser.parse(user_input, utcnow, self.stm.tz_str)
        interval = date-utcnow if date else utcnow # set to error if not defined

        # transfer 
        msg = None

        if interval <= timedelta(hours=0):
            if interval == timedelta(hours=0):
                error_str = info
            else:
                error_str = 'Only dates in the future are allowed.'

            embed = discord.Embed(title='Invalid input date',
                                  color=0xff0000,
                                  description=error_str+'\nPlease try again.')
            view = util.interaction.AckView()
            msg = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await self.transfer_to_message(msg, override_old=True) # after sending the new message, as msg is required

            await view.wait()

        else:
            # success
            localized_date = date.replace(tzinfo=tz.UTC).astimezone(tz.gettz(self.stm.tz_str))

            eb = discord.Embed(title=f'New {action_str}',
                           description='Do you want to add the date `{:s}`? as a new {:s}.'\
                                        .format(localized_date.strftime('%Y-%m-%d %H:%M %Z'), action_str))
            view = util.interaction.ConfirmDenyView(dangerous_action=False)

            msg = await interaction.response.send_message(embed=eb, view=view, ephemeral=True)
            await self.transfer_to_message(msg, override_old=True) # after sending the new message, as msg is required

            await view.wait()

            if view.value:
                # store the non-localized date to db
                if mode == RuleMode.DATE_ADD:
                    self.reminder = lib.ReminderRepeater.add_rules(self.reminder, rdate=date)
                else:
                    self.reminder = lib.ReminderRepeater.add_rules(self.reminder, exdate=date)


        # return to normal view in any case
        eb = self.get_embed()
        self.update_btn_activation() # update in case too many rules are present
        msg = await self.message.edit_original_message(embed=eb, view=self)



    @discord.ui.button(label='Add Repeating Rule', style=discord.ButtonStyle.secondary, row=1)
    async def add_rrule(self, button:  discord.ui.Button, interaction: discord.Interaction):

        modal = RuleModal(field='Enter a new `RRULE`', 
                            title='Add Repeating Rule',
                            custom_callback=self.rrule_callback,
                            mode=RuleMode.RRULE_ADD)

        await interaction.response.send_modal(modal)



    @discord.ui.button(label='Add Exception Rule', style=discord.ButtonStyle.secondary, row=1)
    async def add_rrule_ex(self, button:  discord.ui.Button, interaction: discord.Interaction):
        
        modal = RuleModal(field='Reminder will *not* trigger on this rule', 
                            title='Add Exception Rule',
                            custom_callback=self.rrule_callback,
                            mode=RuleMode.RRULE_EX_ADD)
        await interaction.response.send_modal(modal)



    @discord.ui.button(label='Add Single Date', style=discord.ButtonStyle.secondary, row=2)
    async def add_single(self, button:  discord.ui.Button, interaction: discord.Interaction):
        
        modal = RuleModal(field='Enter a new date (fuzzy or iso)',
                            title='Add a single occurrence date',
                            custom_callback=self.date_callback,
                            mode=RuleMode.DATE_ADD)
        await interaction.response.send_modal(modal)


    @discord.ui.button(label='Add Exception Date', style=discord.ButtonStyle.secondary, row=2)
    async def add_single_ex(self, button:  discord.ui.Button, interaction: discord.Interaction):
        
        modal = RuleModal(field='Enter an exclusion date (fuzzy or iso)',
                            title='Add a single exclusion date',
                            custom_callback=self.date_callback,
                            mode=RuleMode.DATE_ADD)
        await interaction.response.send_modal(modal)

  

    @discord.ui.button(label='Return', style=discord.ButtonStyle.secondary, row=3)
    async def return_btn(self, button:  discord.ui.Button, interaction: discord.Interaction):

        self.disable_all()
        await interaction.response.edit_message(view=self) # in case menu timeous out
        self.stop() # this will give back controll to the list menu




class ReminderEditView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm, message=None, *args, **kwargs):
        super().__init__(message, *args, **kwargs)

        self.reminder = reminder
        self.stm = stm

        if isinstance(reminder, IntervalReminder):
            self.set_interval.label = 'Edit Interval' # override decorator

    def get_embed(self) -> discord.Embed:
        return self.reminder.get_info_embed(self.stm.tz_str)


    @discord.ui.button(label='Edit Channel', style=discord.ButtonStyle.primary)
    async def edit_channel(self, button:  discord.ui.Button, interaction: discord.Interaction):
        pass


    @discord.ui.button(label='Set Interval', style=discord.ButtonStyle.primary)
    async def set_interval(self, button:  discord.ui.Button, interaction: discord.Interaction):

        if isinstance(self.reminder, IntervalReminder):
            view = ReminderIntervalModifyView(self.reminder, self.stm, message=self.message)
        else:
            view = ReminderIntervalAddView(self.reminder, self.stm, message=self.message)

        # TODO: debug
        view = ReminderIntervalAddView(self.reminder, self.stm, message=self.message)

        eb = view.get_embed()
        await interaction.response.edit_message(embed=eb, view=view)


        # wait for end of interaction
        await view.wait()
        self.message = view.message # update own message, in case it was transferred

        # go back to reminder edit view
        eb = self.get_embed()
        await self.message.edit_original_message(embed=eb, view=self)


    @discord.ui.button(label='Return', style=discord.ButtonStyle.secondary, row=2)
    async def ret_menu(self, button:  discord.ui.Button, interaction: discord.Interaction):

        self.disable_all()
        await interaction.response.edit_message(view=self) # in case menu timeous out
        self.stop() # this will give back controll to the list menu


    @discord.ui.button(label='Delete', style=discord.ButtonStyle.danger, row=2)
    async def delete_reminder(self, button:  discord.ui.Button, interaction: discord.Interaction):
        
        view = util.interaction.ConfirmDenyView(dangerous_action=True)
        eb = self.get_embed()
        eb.title = 'Delete Reminder?'
        await interaction.response.edit_message(embed=eb, view=view)

        await view.wait()

        if view.value:
            # delete the reminder
            Connector.delete_interval(self.reminder._id)
            Analytics.interval_deleted(Types.DeleteAction.LISTING)

        self.disable_all()
        await interaction.edit_original_message(view=self) # in case menu timeous out
        self.stop()