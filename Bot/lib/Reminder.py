import discord # for reminder
from datetime import datetime
import dateutil.rrule as rr

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
        d['author'] = str(self.author) if self.author else None
        d['last_msg_id'] = str(self.last_msg_id) if self.last_msg_id else None
        
        if self.created_at:
            d['created_at'] = datetime.timestamp(self.created_at)

        if self.at:
            d['at'] = datetime.timestamp(self.at)
        else:
            d['at'] = None

        return d


    def get_string(self):
        """return string description of this reminder

        Args:
            is_dm (bool, optional): deprecated, is ignored

        Returns:
            [type]: [description]
        """

        if self.target == self.author:
            out_str = f'<@!{self.target}> Reminder: {self.msg}'
        else:
            out_str = f'<@!{self.target}> Reminder: {self.msg} (delivered by <@!{self.author}>)'

        out_str += '\n||This reminder can be more beautiful with `Embed Links` permissions||'
        return out_str




    def _get_embed_body(self, title, author=None):
        eb = discord.Embed(title=title, description=f'{self.msg}', color=0xffcc00)

        if self.created_at:
            eb.set_footer(text='created at {:s}'.format(self.created_at.strftime('%Y-%m-%d %H:%M')))

        if author:
            eb.set_author(name=author.display_name, icon_url=author.avatar_url)

        elif self.target != self.author:
            # fallback if author couldn't be determined
            eb.add_field(name='delivered by', value=f'<@!{self.author}>')

        return eb

        

    def get_info_embed(self):
        """return info embed of this reminders
           used for reminder management.
           Shows due-date, instead of link to channel

        Returns:
            [type]: [description]
        """

        eb = self._get_embed_body('Reminder Info')


        if self.author != self.target:
            eb.add_field(name='Target user', value=f'<@!{self.target}>')

        if self.at:
            eb.add_field(name='Due date', value=self.at.strftime('%Y/%m/%d %H:%M'), inline=False)
        else:
            eb.add_field(name='Due date', value='`No future occurrences`', inline=False)

        return eb


    async def get_embed(self, client, is_dm=False):
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

        eb = self._get_embed_body(title, author)

        if self.g_id and self.last_msg_id:
            url = f'https://discord.com/channels/{self.g_id}/{self.ch_id}/{self.last_msg_id}'
            eb.add_field(name='\u200B', value=f'[jump to the chat]({url})')

        return eb



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


    def get_rule_cnt(self):
        """return the amount of rules
           saved for this reminder

        Returns:
            int: number of rules
        """

        return len(self.rrules) + len(self.exrules) +\
                len(self.rdates) + len(self.exdates)


    def get_rule_dicts(self):
        """get a list of dictionaries
           each describing a set rule (or exclusion)

           'label': is a short title of the rule
           'descr': is more descriptive about the rule
        """

        ret = []

        for rule in self.rrules:
            ret.append({'label': 'Reoccurrence Rule', 'descr': rule[-50:], 'default': False})

        for rule in self.exrules:
            ret.append({'label': 'Exclusion Rule', 'descr': rule[-50:], 'default': False})

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


    def next_trigger(self, utcnow):

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


        next_trigger = ruleset.after(utcnow)
        return next_trigger
