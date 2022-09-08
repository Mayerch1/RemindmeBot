import discord
from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz
from unidecode import unidecode
import validators
import logging

import util.interaction
from util.consts import Consts
import util.verboseErrors
import lib.input_parser
import lib.ReminderRepeater
from lib.Reminder import Reminder, IntervalReminder
from lib.Connector import Connector
from lib.Analytics import Analytics, Types

log = logging.getLogger('Remindme.Listing')


class STMState(Enum):
        INIT=0

class STM():
    def __init__(self, ctx, scope):
        self.ctx: discord.ApplicationContext=ctx
        self.scope:Connector.Scope=scope
        self.state:STMState = STMState.INIT
        self.page:int=0
        self.reminders:list[Reminder] = []
        self.tz_str:str = None


class ReminderChannelEdit(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm: STM, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.reminder = reminder
        self.stm = stm

        self.select_btn.disabled=True
        self.drop_down:discord.ui.Select = None
        self.dd_is_category = False  # is True when drop down holds categories, False on text channels
        self.drop_down_cat=None  # id of selected category, if dd holds text channels, on category mode: don't care

        self.update_category_dropdown()


    def get_embed(self) -> discord.Embed:
        return self.reminder.get_info_embed(self.stm.tz_str)


    async def category_selected_callback(self, interaction: discord.Interaction):
        # only execute when called from category type dd
        # NOP when called from text-channel populated DD
        if self.dd_is_category:
            cat_id = interaction.data['values'][0] # min/max selection is 1
            self.drop_down_cat = int(cat_id)
            await self.update_channel_dropdown(int(cat_id))


    async def update_channel_dropdown(self, category_id: int):

        dd_search = [x for x in self.children if isinstance(x, discord.ui.Select)]
        dropDown_instance = dd_search[0] if dd_search else None

        shown_channels = []

        if self.drop_down_cat == -1:
            shown_channels = list(filter(lambda ch: (isinstance(ch, discord.TextChannel) or isinstance(ch, discord.VoiceChannel)) and ch.category_id is None, self.stm.ctx.guild.channels))
        else:
            # limit to 25 entries
            shown_channels = list(filter(lambda ch: (isinstance(ch, discord.TextChannel) or isinstance(ch, discord.VoiceChannel)) and ch.category_id is not None and ch.category_id==self.drop_down_cat, self.stm.ctx.guild.channels))[0:25]

        rule_options = [discord.SelectOption(
                    label=(('#️⃣ ' if isinstance(c, discord.TextChannel) else '🔉 ') + unidecode(c.name)[:23]) or '*unknown channel name*',
                    value=str(c.id),
                    default=(c.id==self.reminder.ch_id)) for c in shown_channels]
        
        # delet old dropdown
        #self.children.remove(dropDown_instance)
        dropDown_instance.placeholder = 'Select a text-channel'
        if not rule_options:
            dropDown_instance.options = [
                discord.SelectOption(
                    label='*No channels found*',
                    value='-1',
                    default=False
                )
            ]
            self.select_btn.disabled = True # no items to be selected, user needs to cancel
        else:
            
            dropDown_instance.options = []
            for opt in rule_options:
                dropDown_instance.append_option(opt)
            self.select_btn.disabled = False
        
        self.dd_is_category = False
        await self.message.edit_original_message(view=self)


    def update_category_dropdown(self):
        # show only the first 25 categories
        cat_list = list(filter(lambda ch: isinstance(ch, discord.CategoryChannel), self.stm.ctx.guild.channels))[0:24]
        rule_options = [
                discord.SelectOption(
                    label='No category',
                    value=str(-1),
                    default=False
                )
            ]
        rule_options.extend([discord.SelectOption(
                            label=unidecode(c.name)[:25] or '*unknown category name*',
                            value=str(c.id),
                            default=False) for c in cat_list])


        self.drop_down = discord.ui.Select(
                placeholder='Select a category',
                min_values=1,
                max_values=1,
                options=rule_options,
                row=1
            )
        self.drop_down.callback = self.category_selected_callback
        #self.drop_down.callback = self.drop_callback
        self.select_btn.disabled = True # if items in list, enable select btn
        self.add_item(self.drop_down)
        
        self.dd_is_category = True


    @discord.ui.button(label='Select', style=discord.ButtonStyle.green, row=2)
    async def select_btn(self, button:  discord.ui.Button, interaction: discord.Interaction):
        embed=None
        view=None


        if self.drop_down.values:
            new_ch_id = int(self.drop_down.values[0])

            try:
                new_ch = await self.stm.ctx.bot.fetch_channel(new_ch_id)
            except discord.errors.Forbidden:
                new_ch = None

            

            err_eb = None
            if not new_ch:
                err_eb = discord.Embed(title='Failed to edit Reminder',
                                description='Couldn\'t resolve the selected channel. Ensure that I have sufficient permissions.')
            elif isinstance(new_ch, discord.CategoryChannel):
                err_eb = discord.Embed(title='Failed to edit Reminder',
                                description='You must select a Voice- or Text- Channel')
            else:
                r_type = Connector.get_reminder_type(self.stm.scope.instance_id)
                if r_type == Connector.ReminderType.TEXT_ONLY:
                    req_perms = discord.Permissions(send_messages=True)
                    has_perms = util.verboseErrors.VerboseErrors.has_permission(req_perms, new_ch)
                else:
                    has_perms = util.verboseErrors.VerboseErrors.can_send_messages(new_ch)

                if not has_perms:
                    # no permissions
                    err_eb = discord.Embed(title='Failed to set new Channel',
                                            description='Missing permissions in the new channel',
                                            color=Consts.col_err)
            
            if err_eb:
                view = util.interaction.AckView(dangerous_action=True)
                await interaction.response.edit_message(embed=err_eb, view=view)
                await view.wait()
                
            else:
                view = util.interaction.ConfirmDenyView()
                eb = discord.Embed(title='New Notification Channel',
                                    description=f'Do you want to deliver this reminder to `{new_ch.name}`')

                await interaction.response.edit_message(embed=eb, view=view)
                await view.wait()

                if view.value:
                    # store the channel change
                    Connector.set_reminder_channel(self.reminder._id, new_ch_id, new_ch.name)
                    # update local reminder obj
                    self.reminder.ch_id = new_ch_id

        else:
            log.error('channel dropdown had an empty selection')
            view = util.interaction.AckView(dangerous_action=True)
            embed = discord.Embed(title='Reminder Channel not changed',
                                    description='You need to set the dropdown to a *different* existing channel',
                                    color=Consts.col_warn)
            await interaction.response.edit_message(embed=embed, view=view)
            await view.wait()
  

        # go back to normal view
        self.disable_all()
        await self.message.edit_original_message(view=self) # in case of timeout
        self.stop()

            


    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, row=2)
    async def cnacel_btn(self, button:  discord.ui.Button, interaction: discord.Interaction):
        self.disable_all()
        await interaction.response.edit_message(view=self) # in case menu timeous out
        self.stop() # this will give back controll to the list menu

    

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



class EditModal(discord.ui.Modal):
    def __init__(self, reminder: Reminder, tz_str:str, custom_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = None
        self.custom_callback = custom_callback
        self.message = None
        self.reminder = reminder
        self.tz = tz_str


        self.add_item(
            discord.ui.InputText(
                label='Title',
                placeholder='(optional)',
                value=self.reminder.title,
                required=False,
                style=discord.InputTextStyle.singleline
            )
        )
        self.add_item(discord.ui.InputText(
                label='Content',
                value=self.reminder.msg,
                required=True,
                style=discord.InputTextStyle.paragraph
            )
        )
        self.add_item(discord.ui.InputText(
            label='Image Url (optional)',
            value=self.reminder.img_url,
            required=False,
            style=discord.InputTextStyle.singleline
        ))

        if not isinstance(self.reminder, IntervalReminder):
            self.add_item(discord.ui.InputText(
                label='Remind at (iso)',
                value=self.reminder.at.replace(tzinfo=tz.UTC).astimezone(tz=tz.gettz(tz_str)).isoformat(), # add +02:00 for server timezone
                required=True,
                style=discord.InputTextStyle.singleline
                )
            )
        else:
            self.add_item(discord.ui.InputText(
                label='Remind at',
                placeholder='Edit Intervals with `/reminder_list`',
                required=False,
                style=discord.InputTextStyle.singleline
                )
            )


    async def callback(self, interaction: discord.Interaction):

        info = ''

        # title
        new_title = self.children[0].value
        new_msg = self.children[1].value
        new_imgurl = self.children[2].value
        new_at = self.children[3].value
        
        if new_title != self.reminder.title:
            self.reminder.title = new_title
            Connector.set_reminder_title(self.reminder._id, self.reminder.title)

        if new_msg != self.reminder.msg:
            self.reminder.msg = new_msg
            Connector.set_reminder_message(self.reminder._id, self.reminder.msg)

        if new_imgurl != self.reminder.img_url:
            # check if the given url is actually valid
            try:
                success = validators.url(new_imgurl)
            except:
                success = False
                pass
            if success:
                self.reminder.img_url = new_imgurl
                Connector.set_reminder_img_url(self.reminder._id, self.reminder.img_url)


        if not isinstance(self.reminder, IntervalReminder):
            # check if valid iso-date was added
            try:
                parsed_at = datetime.strptime(new_at, '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                try:
                    parsed_at = datetime.strptime(new_at, '%Y-%m-%dT%H:%M:%S.%f%z')
                except ValueError:
                    info += 'Didn\'t change the reminder date. The date is not an ISO-timestamp.\n'
                    # TODO: show parsing error
                    parsed_at = None

            if parsed_at:
                new_at_utc = parsed_at.astimezone(tz=tz.UTC).replace(tzinfo=None) if parsed_at.tzinfo else parsed_at
                self.reminder.at = new_at_utc
                Connector.update_reminder_at(self.reminder)
        else:
            if new_at:
                # TODO: check if placeholder is assigned to new_at or if None
                info += 'The `Interval` attribute must be edited with `Edit Interval`.\n'


        if self.custom_callback:
            await self.custom_callback(interaction)
        else:
            await interaction.response.send_message(info+'Use `Set/Edit Interval` for better date parsing', ephemeral=True)

        self.stop()


class ReminderIntervalAddView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm: STM, message, *args, **kwargs):
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


class ReminderIntervalModifyView(util.interaction.CustomView):
    def __init__(self, reminder: IntervalReminder, stm, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)

        self.reminder: IntervalReminder = reminder
        self.stm = stm
        self.rule_index:int = None

        # this button possibly can't be active w/o selection
        self.del_rule.disabled=True

        # populate the dropdown selection
        self.update_dropdown()



    def get_embed(self, rule_id:int=None) -> discord.Embed:

        rules = self.reminder.get_rule_dicts()
    
        if self.rule_index is None:
            descr = 'You can show more detailed information for existing rules.'\
                            'You can aswell delete selected rules/dates'
        else:
            descr = rules[self.rule_index]['descr']

        return discord.Embed(
            title='Show/Delete existing rules',
            description=descr
        )


    def update_dropdown(self):
        rules = self.reminder.get_rule_dicts()

        dd_search = [x for x in self.children if isinstance(x, discord.ui.Select)]

        rule_options = [discord.SelectOption(
                        label=r['label'], 
                        description=r['descr'], 
                        value=str(i),
                        default=(i==self.rule_index)) for i, r in enumerate(rules)]

        if dd_search and rule_options:
            dd = dd_search[0]
            dd.options = []
            for opt in rule_options:
                dd.append_option(opt)
        elif dd_search and not rule_options:
            # delete action row
            self.children.remove(dd_search[0])
        elif rule_options:
            self.drop_down = discord.ui.Select(
                placeholder='Select a rule/date for more info',
                min_values=1,
                max_values=1,
                options=rule_options,
                row=1
            )
            self.drop_down.callback = self.drop_callback
            self.add_item(self.drop_down)
        
        # else pass


    @discord.ui.button(label='Add New Rule', style=discord.ButtonStyle.primary, row=2)
    async def add_rule(self, button:  discord.ui.Button, interaction: discord.Interaction):
        view = ReminderIntervalAddView(self.reminder, self.stm, self.message)
        eb = view.get_embed()

        await interaction.response.edit_message(embed=eb, view=view)
        await view.wait()

        self.message = view.message # in case of migration

        # go back to current menu
        self.rule_index=None
        self.del_rule.disabled=True
        eb = self.get_embed()
        self.update_dropdown()
        await self.message.edit_original_message(embed=eb, view=self)



    @discord.ui.button(label='Delete Selected', style=discord.ButtonStyle.danger, row=2)
    async def del_rule(self, button:  discord.ui.Button, interaction: discord.Interaction):

        rules = self.reminder.get_rule_dicts()
        rule_descr = rules[self.rule_index]['descr']
        
        view = util.interaction.ConfirmDenyView(dangerous_action=True)
        embed = discord.Embed(
            title='Danger',
            description=f'Are you sure to delete the rule `{rule_descr}`?',
            color=0xff0000
        )

        await interaction.response.edit_message(embed=embed, view=view)
        await view.wait()

        if view.value:
            # go aheaad with deletion
            self.reminder = lib.ReminderRepeater.rm_rules(self.reminder, rule_idx=self.rule_index)

            if not self.reminder.at:
                eb = discord.Embed(title='Orphan warning',
                    color=0xaa3333,
                    description='The reminder has no further events pending. It will be deleted soon, if no new rule is added')
                view = util.interaction.AckView(dangerous_action=True)

                await self.message.edit_original_message(embed=eb, view=view)
                await view.wait()
        

        # test if there're any rules left
        if isinstance(self.reminder, IntervalReminder):
            # return back to normal view in any case
            self.rule_index=None
            self.del_rule.disabled=True
            eb = self.get_embed()
            self.update_dropdown()
            await self.message.edit_original_message(embed=eb, view=self)
        else:
            self.disable_all()
            await interaction.edit_original_message(view=self) # in case menu timeous out
            self.stop() # this will give back controll to the list menu
    


    @discord.ui.button(label='Return', style=discord.ButtonStyle.secondary, row=3)
    async def return_btn(self, button:  discord.ui.Button, interaction: discord.Interaction):

        self.disable_all()
        await interaction.response.edit_message(view=self) # in case menu timeous out
        self.stop() # this will give back controll to the list menu



    async def drop_callback(self, interaction: discord.Interaction):
        sel = interaction.data['values'][0] # min_select 1
        self.rule_index = int(sel)

        # update the embed with the rule details
        self.del_rule.disabled=False
        eb = self.get_embed()
        self.update_dropdown()
        await interaction.response.edit_message(embed=eb, view=self)




class ReminderEditView(util.interaction.CustomView):
    def __init__(self, reminder: Reminder, stm, message=None, *args, **kwargs):
        super().__init__(message, *args, **kwargs)

        self.reminder = reminder
        self.stm = stm

        self._override_edit_label()

        if self.stm.scope.is_private:
            # private reminders cannot change the channel
            self.edit_channel.disabled=True


    def _override_edit_label(self):
        if isinstance(self.reminder, IntervalReminder):
            self.set_interval.label = 'Edit Interval' # override decorator
        else:
            self.set_interval.label = 'Set Interval'


    def get_embed(self) -> discord.Embed:
        return self.reminder.get_info_embed(self.stm.tz_str)


    @discord.ui.button(label='Edit Channel', style=discord.ButtonStyle.primary)
    async def edit_channel(self, button:  discord.ui.Button, interaction: discord.Interaction):
        
        view = ReminderChannelEdit(self.reminder, self.stm, message=self.message)
        eb = view.get_embed()

        await interaction.response.edit_message(embed=eb, view=view)
        await view.wait()
        self.message = view.message # in case of migration

        # go back to normal view
        eb = self.get_embed()
        await self.message.edit_original_message(embed=eb, view=self)



    @discord.ui.button(label='Set Interval', style=discord.ButtonStyle.primary)
    async def set_interval(self, button:  discord.ui.Button, interaction: discord.Interaction):

        if isinstance(self.reminder, IntervalReminder):
            view = ReminderIntervalModifyView(self.reminder, self.stm, message=self.message)
        else:
            view = ReminderIntervalAddView(self.reminder, self.stm, message=self.message)
    

        eb = view.get_embed()
        await interaction.response.edit_message(embed=eb, view=view)


        # wait for end of interaction
        await view.wait()
        self.message = view.message # update own message, in case it was transferred
        self.reminder = view.reminder

        # go back to reminder edit view
        self._override_edit_label()
        eb = self.get_embed()
        await self.message.edit_original_message(embed=eb, view=self)


    @discord.ui.button(label='Edit', emoji='🛠️', style=discord.ButtonStyle.secondary)
    async def edit_reminder_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        modal = EditModal(reminder=self.reminder, 
                                                    custom_callback=None,
                                                    tz_str=self.stm.tz_str,
                                                    title='Edit the Reminder')

        await interaction.response.send_modal(modal)
        await modal.wait()

        if isinstance(self.reminder, IntervalReminder):
            self.reminder = Connector.get_interval_by_id(self.reminder._id)
        else:
            self.reminder = Connector.get_reminder_by_id(self.reminder._id)

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
            if isinstance(self.reminder, IntervalReminder):
                Connector.delete_interval(self.reminder._id)
                Analytics.interval_deleted(Types.DeleteAction.LISTING)
            else:
                Connector.delete_reminder(self.reminder._id)
                Analytics.reminder_deleted(Types.DeleteAction.LISTING)

            # go back to previous view
            self.disable_all()
            

        await interaction.edit_original_message(embed=self.get_embed(), view=self)
        if view.value:
            self.stop() # must be after last edit