from datetime import datetime
from dateutil import tz
import dateutil.rrule as rr

from lib.Connector import Connector
from lib.Analytics import Analytics
from lib.Reminder import Reminder, IntervalReminder


#====================
# Transformation Ops
#====================

def _reminder_to_interval(reminder: Reminder):
    """convert the Reminder into an IntervalReminder
       push transaction onto db
       return new IntervalReminder Object
       WARN: reminder might be orphaned and requires rules to be added

    Args:
        reminder (Reminder): old reminder       

    Returns:
        IntervalReminder: new reminder object
    """

    # create new IntervalReminder
    old_reminder = reminder
    reminder = IntervalReminder(old_reminder._to_json())

    # update the occurrence to optimise database fetches
    reminder.first_at = old_reminder.at
    # keep reminder 'at' at old val for now

    new_id = Connector.add_interval(reminder)
    Connector.delete_reminder(old_reminder._id)

    Analytics.reminder_created(reminder)

    reminder._id = new_id
    return reminder



def _interval_to_reminder(reminder: IntervalReminder):

    old_reminder = reminder
    reminder = Reminder(reminder._to_json())
    reminder.at = old_reminder.first_at

    new_id = Connector.add_reminder(reminder)
    Connector.delete_interval(old_reminder._id)
    
    Analytics.reminder_created(reminder, from_interval=True)

    reminder._id = new_id
    return reminder



def add_rules(reminder, rrule=None, exrule=None, rdate=None, exdate=None) -> IntervalReminder:
    """add the given rules to the given reminder
       converts the reminder to Intevral if not done yet

    Args:
        reminder (_type_): _description_
        rrule (_type_, optional): _description_. Defaults to None.
        exrule (_type_, optional): _description_. Defaults to None.
        rdate (_type_, optional): _description_. Defaults to None.
        exdate (_type_, optional): _description_. Defaults to None.

    Returns:
        IntervalReminder: the converted  reminder
    """

    if type(reminder) == Reminder:
        reminder = _reminder_to_interval(reminder)

    if rrule:
        reminder.rrules.append(rrule)
    
    if exrule:
        reminder.exrules.append(exrule)

    if rdate:
        reminder.rdates.append(rdate)

    if exdate:
        reminder.exdates.append(exdate)


    reminder.at = reminder.next_trigger(datetime.utcnow())
    Connector.update_interval_rules(reminder)
    Connector.update_interval_at(reminder)

    Analytics.ruleset_added()

    return reminder


def rm_rules(reminder: IntervalReminder, rule_idx=None):

    utcnow = datetime.utcnow()

    if rule_idx is None:
        return reminder

    reminder.delete_rule_idx(rule_idx)
    reminder.at = reminder.next_trigger(datetime.utcnow())

    rules_cnt = reminder.get_rule_cnt()

    # if reminder has no further rules left over
    # and .at is in the future, set it as default Reminder
    if rules_cnt == 0 and reminder.at and reminder.at > utcnow:
        reminder = _interval_to_reminder(reminder)
        Analytics.ruleset_removed()
        return reminder

    # if reminder has no further occurrence
    # it is kept as orphaned reminder
    # it may or may not have some rules set
    # it's deleted in both cases within the next 24h

    # if at is None
    # the reminder is orphaned, a warning can be displayed by a higher layer
    Connector.update_interval_rules(reminder)
    Connector.update_interval_at(reminder)
    Analytics.ruleset_removed()

    return reminder


def _rule_normalize(rule_str, dtstart):
    """generate the rrule of the given rrule string
       if the string contains timezone based offsets (iso dates)
       they are converted into the non-timezone aware utc equivalent

    Args:
        rule_str ([type]): [description]
        dtstart ([type]): [description]

    Returns:
        [type]: [description]
    """

    try:
        rule = rr.rrulestr(rule_str)
    except Exception as e:
        return None, str(e)

    until = rule._until
    until_utc = None

    if until:
        # convert the until date to non-tz aware
        until_utc = until.astimezone(tz.UTC)
        until_utc = until_utc.replace(tzinfo=None)

    try:
        rule = rr.rrulestr(rule_str, dtstart=dtstart, ignoretz=True)
    except Exception as e:
        return None, str(e)

    if until_utc:
        rule = rule.replace(until=until_utc)

    return rule, None


