import discord # for reminder
from datetime import datetime
from dateutil import tz
import dateutil.rrule as rr

import lib.input_parser
import lib.Connector  # KEEP this syntax, circular import

class Reminder:

    def __init__(self, json = {}):
        if not json:
            json = {}

        self.msg = json.get('msg', None)

        self._id = json.get('_id', None)

        g_id = json.get('g_id', None)
        self.g_id = int(g_id) if g_id else None

        ch_id = json.get('ch_id', None)
        self.ch_id = int(ch_id) if ch_id else None

        target = json.get('target', None)
        self.target = int(target) if target else None

        self.target_mention = json.get('target_mention', None)
        self.target_name = json.get('target_name', None)
        self.ch_name = json.get('ch_name', None)

        author = json.get('author', None)
        self.author = int(author) if author else None

        last_msg_id = json.get('last_msg_id', None)
        self.last_msg_id = int(last_msg_id) if last_msg_id else None

        self.at = json.get('at', None)
        if self.at:
            self.at = datetime.fromtimestamp(self.at)

        self.created_at = json.get('created_at', None)
        if self.created_at:
            self.created_at = datetime.fromtimestamp(self.created_at)


    def __eq__(self, other):
        # equals allows None
        return self.at == other.at

    def __lt__(self, other):
        return (self.at or datetime.utcnow()) < (other.at or datetime.utcnow())

    def __le__(self, other):
        return (self.at or datetime.utcnow()) <= (other.at or datetime.utcnow())

    def __gt__(self, other):
        return (self.at or datetime.utcnow()) > (other.at or datetime.utcnow())

    def __ge__(self, other):
        return (self.at or datetime.utcnow()) >= (other.at or datetime.utcnow())

    def __ne__(self, other):
        # unequals allows None
        return self.at != other.at


    def _to_json(self):
        d = dict()

        d['msg'] = self.msg

        d['g_id'] = str(self.g_id) if self.g_id else None
        d['ch_id'] = str(self.ch_id) if self.ch_id else None
        d['target'] = str(self.target) if self.target else None
        d['target_mention'] = self.target_mention
        d['target_name'] = self.target_name
        d['ch_name'] = self.ch_name
        d['author'] = str(self.author) if self.author else None
        d['last_msg_id'] = str(self.last_msg_id) if self.last_msg_id else None
        
        if self.created_at:
            d['created_at'] = datetime.timestamp(self.created_at)

        if self.at:
            d['at'] = datetime.timestamp(self.at)
        else:
            d['at'] = None

        return d


    
    def get_interval_string(self, now=None, use_timestamp=False):
        """get a string describing the interval until reminder is triggered
           if self.at is None, returns verbose string showing no future occurrence

        Returns:
            [str]: [description]
        """

        if not self.at:
            return 'No future occurrence'
        
        if not now:
            now = datetime.utcnow()  
            
            
        if use_timestamp:
            at = self.at.replace(tzinfo=tz.UTC)
            return f'<t:{int(at.timestamp())}:R>'
          
        delta = self.at - now
        total_secs = int(max(0, delta.total_seconds()))

        hours, rem = divmod(total_secs, 3600)
        mins, secs = divmod(rem, 60)
        
        days, rem = divmod(total_secs, 3600*24)
        hour_days = int(rem/3600)
        
        weeks, rem = divmod(total_secs, 3600*24*7)
        days_weeks = int(rem/(3600*24))
        
        years, rem = divmod(total_secs, 3600*24*365)
        weeks_years = int(rem/(3600*24*7))


        if weeks > 104:
            return '{:d} years and {:d} weeks'.format(years, weeks_years)
        elif weeks > 10:
            return '{:d} weeks and {:d} days'.format(weeks, days_weeks)
        elif days > 14:
            return '{:d} days and {:d} hours'.format(days, hour_days)
        elif hours > 48:
            return '{:d} days ({:02d} hours)'.format(int(hours/24), int(hours))
        elif hours > 0:
            return '{:02d} h {:02d} m'.format(int(hours), int(mins))
        else:
            return '{:d} minutes'.format(int(mins))


    async def get_string(self, client=None, is_dm=False):
        """return string description of this reminder

        Args:
            is_dm (bool, optional): deprecated, is ignored

        Returns:
            [type]: [description]
        """

        # only get the author object
        # if the author is actually required
        author = None
        if self.author != self.target:
            try:
                author = await client.fetch_user(self.author)
            except discord.errors.NotFound:
                pass

        if not is_dm:
            out_str = self.target_mention or f'<@!{self.target}>'
        else:
            out_str = ''

        if self.target == self.author:
            out_str += f' {self.msg}'
        elif author:
            out_str += f' {self.msg} (by {author.display_name})'
        else:
            out_str += f' {self.msg} (by <@!{self.author}>)'

        return out_str


    def _get_embed_body(self, title, author=None, tz_str='UTC'):
        eb = discord.Embed(title=title, description=f'{self.msg}', color=0xe4ff1e)

        if self.created_at:
            if tz_str == 'UTC':
                at_str = self.created_at.strftime('%Y-%m-%d %H:%M UTC')
            else:
                at_str = self.created_at.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str)).strftime('%Y/%m/%d %H:%M %Z')

            eb.timestamp = self.created_at
            eb.set_footer(text='created: ')

        if author:
            eb.set_author(name=author.display_name, icon_url=author.avatar_url)
        elif self.target != self.author:
            # fallback if author couldn't be determined
            eb.add_field(name='by', value=f'<@!{self.author}>', inline=False)

        return eb
    

    def get_tiny_embed(self, title='New Reminder Created', now=None, info=None, rrule_override=None):
        """return a tiny info embed of the reminder
           used upon reminder creation, to not bloat main chat
           Show interval till next/first trigger
           
           rrule_override is ignored

        Returns:
            [type]: [description]
        """

        if not now:
            now = datetime.utcnow()
        
        if self.target == self.author:
            description = 'Reminding you '
        else:
            tgt_str = self.target_name or f'<@!{self.target}>'
            description = f'Reminding {tgt_str} '
 
        
        at_utc = self.at.replace(tzinfo=tz.UTC)
        description += f'<t:{int(at_utc.timestamp())}:R>'
        
        if info:
            description += f'\n```Parsing hints:\n{info}```' 
    
        eb = discord.Embed(title=title, description=description, color=0x409fe2)
        eb.timestamp = at_utc

        return eb


    def get_info_embed(self, tz_str='UTC', title='Reminder Info'):
        """return info embed of this reminders
           used for reminder management.
           Shows due-date, instead of link to channel

        Returns:
            [type]: [description]
        """

        eb = self._get_embed_body(title, tz_str=tz_str)
        eb.color = 0x409fe2


        if self.author != self.target:
            eb.add_field(name='Target user/role', value=self.target_name or f'<@!{self.target}>')

        if self.at:
            at_utc = self.at.replace(tzinfo=tz.UTC)
            at_ts = int(at_utc.timestamp())
            at_str = f'<t:{at_ts}> <t:{at_ts}:R>'
        else:
            at_str = '`No future occurrences`'

        eb.add_field(name='Due date', value=at_str, inline=False)

        return eb


    async def get_embed(self, client, is_dm=False, tz_str='UTC'):
        """return embed of this reminders
           will resolve user mentions.
           Used for elapsed reminders

        Args:
            client ([type]): bot client object, for resolving user names
            is_dm (bool, optional): legacy, is ignored

        Returns:
            discord.Embed: embed of reminder
        """

        if self.target != self.author:
            try:
                author = await client.fetch_user(self.author)
                title = 'Reminds you'
            except discord.errors.NotFound:
                author = None
                title = f'Reminder'
        else:
            author = None
            title = f'Reminder'

        eb = self._get_embed_body(title, author=author, tz_str=tz_str)

        if self.g_id and self.last_msg_id:
            url = f'https://discord.com/channels/{self.g_id}/{self.ch_id}/{self.last_msg_id}'
            eb.add_field(name='\u200B', value=f'[jump to the chat]({url})', inline=False)
        elif self.last_msg_id:
            # private dm
            url = f'https://discord.com/channels/@me/9/{self.last_msg_id}'
            eb.add_field(name='\u200B', value=f'[jump to the chat]({url})', inline=False)

        return eb


    def get_embed_text(self, is_dm=False):
        """returns a short text intented to be sent in combination 
           with the get_embed
           
           holds a mention for the user/role and the beginning of the reminder message
        """
        
        if not is_dm:
            tmp = self.target_mention or f'<@{self.target}>'
        else:
            tmp = ''

        tmp += ' '
        tmp += self.msg if len(self.msg) < 100 else f'{self.msg[0:100]} [...]'

        return tmp

class IntervalReminder(Reminder):
    
    def __init__(self, json = {}):
        if not json:
            json = {}

        super().__init__(json)


        self.first_at = json.get('first_at', None)
        if self.first_at:
            self.first_at = datetime.fromtimestamp(self.first_at)

        self.exdates = json.get('exdates', [])
        self.exrules = json.get('exrules', [])
        self.rdates = json.get('rdates', [])
        self.rrules = json.get('rrules', [])


    def _to_json(self):
        d = super()._to_json()

        d['exdates'] = self.exdates
        d['exrules'] = self.exrules
        d['rdates'] = self.rdates
        d['rrules'] = self.rrules

        if self.first_at:
            d['first_at'] = datetime.timestamp(self.first_at)

        return d


    def get_tiny_embed(self, title='New Interval Created', now=None, info=None, rrule_override=None):
        """return a tiny info embed of the reminder
           used upon reminder creation, to not bloat main chat
           Show interval till next/first trigger

        Returns:
            [type]: [description]
        """

        if not now:
            now = datetime.utcnow()
        
        if self.target == self.author:
            description = 'Reminding you '
        else:
            tgt_str = self.target_name or f'<@!{self.target}>'
            description = f'Reminding {tgt_str} '

        description += f'the first time {self.get_interval_string(now, use_timestamp=True)}'
        description += '\n\nCall `/reminder_list` to edit all pending reminders'
        
        if info:
            description += f'\n```Parsing hints:\n{info}```' 
    
        eb = discord.Embed(title=title, description=description, color=0x409fe2)
        #eb.timestamp = self.at.replace(tzinfo=tz.UTC)
        
        
        if rrule_override:
            rrule = rrule_override
        elif self.rrules:
            rule_str = self.rrules[0]
            rrule = rr.rrulestr(rule_str)
        else:
            rrule = None

        if rrule:
            interval_txt = lib.input_parser.rrule_to_english(rrule, now=now)
        else:
            interval_txt = '\u200b'

        eb.set_footer(text=interval_txt, icon_url='https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/282/repeat-button_1f501.png')
        
        return eb


    def get_info_embed(self, tz_str='UTC', title='Interval Info'):
        """return info embed of this reminders
           used for reminder management.
           Shows due-date, instead of link to channel

        Returns:
            [type]: [description]
        """
        eb = super().get_info_embed(tz_str=tz_str, title=title)
        eb.timestamp = discord.Embed.Empty
        
        in_str = self.get_interval_string()
        prefix = 'Next in ' if self.at else ''
        
        eb.set_footer(text=f'{prefix}{in_str}', icon_url='https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/282/repeat-button_1f501.png')

        return eb


    async def get_embed(self, client, is_dm=False, tz_str='UTC'):
        """return embed of this reminders
           will resolve user mentions.
           Used for elapsed reminders

        Args:
            client ([type]): bot client object, for resolving user names
            is_dm (bool, optional): legacy, is ignored

        Returns:
            discord.Embed: embed of reminder
        """
        
        eb = await super().get_embed(client, is_dm, tz_str)
        
        
        in_str = self.get_interval_string()
        prefix = 'Next in ' if self.at else ''
        postfix = ', created'
        
        eb.set_footer(text=f'{prefix}{in_str}{postfix}', icon_url='https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/282/repeat-button_1f501.png')
        
        return eb


    def get_rule_cnt(self):
        """return the amount of rules
           saved for this reminder

        Returns:
            int: number of rules
        """

        return len(self.rrules) + len(self.exrules) +\
                len(self.rdates) + len(self.exdates)


    def get_rule_dicts(self) -> list:
        """get a list of dictionaries
           each describing a set rule (or exclusion)

           'label': is a short title of the rule
           'descr': is more descriptive about the rule
        """

        ret = []

        for rule in self.rrules:
            ret.append({'label': 'Reoccurrence Rule', 'descr': lib.input_parser.rrule_to_english(rule)[0:50], 'default': False})

        for rule in self.exrules:
            ret.append({'label': 'Exclusion Rule', 'descr': lib.input_parser.rrule_to_english(rule)[0:50], 'default': False})

        for date in self.rdates:
            ret.append({'label': 'Single Occurrence', 'descr': date.strftime('%Y-%m-%d %H:%M'), 'default': False})

        for date in self.exdates:
            ret.append({'label': 'Single Exclusion', 'descr': date.strftime('%Y-%m-%d %H:%M'), 'default': False})
        
        return ret


    def delete_rule_idx(self, rule_idx):

        idx_offset = 0

        max_rrule = len(self.rrules)
        
        if rule_idx < max_rrule:
            del self.rrules[rule_idx]
            return
        idx_offset = max_rrule

        max_exrule = len(self.exrules)
        if rule_idx < max_exrule+idx_offset:
            del self.exrules[rule_idx-idx_offset]
            return
        idx_offset += max_exrule

        max_rdate = len(self.rdates)
        if rule_idx < max_rdate+idx_offset:
            del self.rdates[rule_idx-idx_offset]
            return
        idx_offset += max_rdate

        max_exdate = len(self.exdates)
        if rule_idx < max_exdate+idx_offset:
            del self.exdates[rule_idx-idx_offset]
            return
        idx_offset += max_exdate

        return


    def next_trigger(self, utcnow, tz_str=None):

        instance_id = self.g_id if self.g_id else self.author
        legacy_mode = lib.Connector.Connector.is_legacy_interval(instance_id)

        ruleset = rr.rruleset()

        # the date of the initial remindme
        # is always included by default

        ruleset.rdate(self.first_at)

        for rule in self.rrules:
            ruleset.rrule(rr.rrulestr(rule))

        for rule in self.exrules:
            ruleset.exrule(rr.rrulestr(rule))

        for date in self.rdates:
            ruleset.rdate(date)

        for date in self.exdates:
            ruleset.exdate(date)


        if not legacy_mode:
            # the local time must be used
            # to determin the next event
            if not tz_str:
                tz_str = lib.Connector.Connector.get_timezone(instance_id)

            local_now = utcnow.replace(tzinfo=tz.UTC)
            local_now = local_now.astimezone(tz.gettz(tz_str))
            local_now = local_now.replace(tzinfo=None)
            
            next_trigger = ruleset.after(local_now)
            
            if next_trigger:
                # back to UTC, for DB queries
                next_trigger = next_trigger.replace(tzinfo=tz.gettz(tz_str))
                next_trigger = next_trigger.astimezone(tz.UTC)
                next_trigger = next_trigger.replace(tzinfo=None)
            
        else:
            next_trigger = ruleset.after(utcnow)

    
            
        return next_trigger
