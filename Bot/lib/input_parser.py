import re
import copy
from datetime import datetime, timedelta

import dateutil.parser
from dateutil.relativedelta import *
from dateutil import tz
import dateutil.rrule as rr
from parsedatetime import parsedatetime

from lib.recurrent.src.recurrent.event_parser import RecurringEvent


_parse_consts = parsedatetime.Constants(localeID='en_US', usePyICU=True)
_parse_consts.useMeridian = False
_parse_consts.use24 = True
_parse_consts.dateFormats = {
    'full': 'EEEE, d. MMMM yyyy',
    'long': 'd. MMMM yyyy',
    'medium': 'dd.MM.yyyy',
    'short': 'dd.MM.yy',
}
_parse_consts.timeFormats = {
    'full': 'HH:mm:ss v',
    'long': 'HH:mm:ss z',
    'medium': 'HH:mm:ss',
    'short': 'HH:mm',
}
_parse_consts.dp_order = ['d', 'm', 'y']


def num_to_emoji(num: int):
    """convert a single digit to the numbers emoji
    Arguments:
        num {int}
    Returns:
        [str] -- unicode emoji, * if num was out of range [0..9]
    """
    if num == 1:
        return '1️⃣'
    elif num == 2:
        return '2️⃣'
    elif num == 3:
        return '3️⃣'
    elif num == 4:
        return '4️⃣'
    elif num == 5:
        return '5️⃣'
    elif num == 6:
        return '6️⃣'
    elif num == 7:
        return '7️⃣'
    elif num == 8:
        return '8️⃣'
    elif num == 9:
        return '9️⃣'
    elif num == 0:
        return '0️⃣'
    else:
        return '*️⃣'


def _to_int(num_str: str, base: int=10):
        
    try:
        conv_int = int(num_str, base)
    except ValueError:
        conv_int = None
    finally:
        return conv_int


def _split_arg(arg):

    num_regex = re.search(r'-?\d+', arg)

    if num_regex:
        num_arg = num_regex.group()

        return (int(num_arg), arg.replace(num_arg, ''))
    else:
        return (None, arg)


def _join_spaced_args(args):

    joined_args = []
    
    i = 0
    while i < len(args):
        arg = args[i]

        if i+1 >= len(args):
            # cannot perform operation on last element
            joined_args.append(arg)

        # i+1 is guaranteed to exist
        elif (arg[0] != None and not arg[1]) and (not args[i+1][0] and args[i+1][1]):
            joined_args.append((arg[0], args[i+1][1]))
            i += 1 # skip next element

        else:
            # element is not complete, but following element doesn't allow joinup
            # this is caused by args like eom, eoy, ...
            joined_args.append(arg)
            
        i += 1

    return joined_args
            

def _parse_relative(args, utcnow):
    """parse the date to relative arguments
       (2y, 5d,...)

       gives the absolute utc-date when the reminder
       should be triggered

    Args:
        args ([]]): list of arguments
        utcnow (datetime): current utc datetime

    Returns:
        (datetime, str, exception): non tz-aware date when reminder is trigger (in utc time), =utcnow on error
                                    info string for parsing errors/warnings
                                    exception if one was caught, which is of interest for further processing
    """

    total_intvl = timedelta(hours=0)
    info = ''

    for arg in args:

        intvl = timedelta(hours=0) # default in case of no-match

        if arg[0] == None:
            info = info + f'• Ignoring {arg}, as required numerical part is missing\n'
        else:
            if arg[1].startswith('y'):
                intvl = relativedelta(years=arg[0])

            elif arg[1].startswith('mo'):
                intvl = relativedelta(months=arg[0])

            elif arg[1].startswith('w'):
                intvl = relativedelta(weeks=arg[0])

            elif arg[1] == 'd' or arg[1].startswith('da'):
                # condition must not detect the month 'december'
                intvl = timedelta(days=arg[0]) 

            elif arg[1].startswith('h'):
                intvl = timedelta(hours=arg[0])

            elif arg[1].startswith('mi'):
                intvl = timedelta(minutes=arg[0])
            
            elif arg[1] == 'm':
                intvl = timedelta(minutes=arg[0])
                info = info + f'• Ambiguous reference, \'m\' was interpreted as minutes.\n  Type \'mo\' for months.\n'
            else:
                info = info + f'• Ignoring {arg}, as this is not a known interval\n'
            
        total_intvl += intvl

    try:
        eval_interval = utcnow + total_intvl
    except ValueError as ex:
        return (utcnow, 'The interval is out of bounds/not a number', ex)

    return (eval_interval, info, None)


def _parse_iso(input, utcnow, display_tz):

    try:
        remind_parse = dateutil.parser.isoparse(input)
    except ValueError as e:
        info = '• ' + ' '.join(e.args)
        remind_parse = None
    except:
        info = '• Unexpected parser error occurred'
        remind_parse = None
    else:
        info = ''

    # if the input string doesn't hold any timezone
    # it is converted into the local timzone
    # otherwise not modified
    # error assumes current utc time
    if remind_parse and not remind_parse.tzinfo:
        remind_aware = remind_parse.replace(tzinfo=display_tz)
    elif not remind_parse:
        remind_aware = utcnow.replace(tzinfo=tz.UTC)
    else:
        remind_aware = remind_parse


    # convert the parsed time back into a non-tz aware string
    # at utc
    remind_utc = remind_aware.astimezone(tz.UTC)
    remind_at = remind_utc.replace(tzinfo=None)

    return (remind_at, info, None)


def _parse_fuzzy(input, utcnow, display_tz):
    """parse a fuzzy input string using dateutil

       gives the absolute utc-date when the reminder
       should be triggered

    Args:
        input (str): input string, provided by user
        utcnow (datetime): current utc datetime
        display_tz (tzfile): the timezone of the guild/user

    Returns:
        (datetime, str, exception): non tz-aware date when reminder is trigger (in utc time), =utcnow on error
                         info string for parsing errors/warnings
    """

    info = ''
    localnow = utcnow.replace(tzinfo=tz.UTC).astimezone(display_tz)

    eod_re = re.compile(r'\b(end of day)|eod\b')
    eow_re = re.compile(r'\b(end of week)|eow\b')
    eom_re = re.compile(r'\b(end of month)|eom\b')
    eoy_re = re.compile(r'\b(end of year)|eoy\b')
    
    replace_datetime = None
    matched_regex = None
    
    # remove timezone awareness, on each date w/o converting to utc
    # parser wil assume local time for natural language
    if eod_re.match(input):
        tmp = localnow.replace(hour=0, minute=0, second=0, microsecond=0)
        replace_datetime = tmp + relativedelta(hours=17)  # could be one-liner, but stay consistent with other cases
        matched_regex = eod_re

    elif eow_re.match(input):
        w_day = localnow.weekday()
        tmp = localnow - timedelta(days=w_day)
        tmp = tmp.replace(hour=0, minute=0, second=0, microsecond=0)
        replace_datetime = tmp + relativedelta(days=5, hours=-7)  # 17:00 on last day of week

        matched_regex = eow_re

    elif eom_re.match(input):
        tmp = localnow.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        replace_datetime = tmp + relativedelta(months=1, hours=-12)  # 12:00 on last day of month
        matched_regex = eom_re

    elif eoy_re.match(input):
        tmp = localnow.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        replace_datetime = tmp + relativedelta(years=1, hours=-15)  # 9:00 on last day of year
        matched_regex = eoy_re

    # without regex match, no replacement can happend (obviously)
    if replace_datetime is not None and matched_regex is not None:
        # the absolute date could be called on the last day, but after the default reminding hour
        # for that case, the reminder is pushed back by 2 hours, or by the last millisecond of the day
        # whatever is earlier
        if replace_datetime < localnow:
            delta_option = (localnow + relativedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
            fixed_option = replace_datetime.replace(hour=0) + relativedelta(hours=24, microseconds=-1)
            replace_datetime = min(delta_option, fixed_option)
        
        # disregard the timezone
        replace_datetime = replace_datetime.replace(tzinfo=None)
        # export microseconds here
        # although the parser is ignoring them
        input = matched_regex.sub(replace_datetime.strftime('%d/%m/%Y %H:%M:%S.%f'), input)

    r = RecurringEvent(now_date=localnow, preferred_time_range=(0,12), parse_constants=_parse_consts)
    remind_parse = r.parse(input)

    if remind_parse is None:
        # try additional approach
        # this is mainly executed to get a verbose error message
        # which is not provided by recurrent
        try:
            remind_parse = dateutil.parser.parse(input, fuzzy=True, dayfirst=True, yearfirst=False)
        except dateutil.parser.ParserError as e:
            info = '• ' + ' '.join(e.args)
            remind_parse = None
        except Exception as e:
            remind_parse = None
            info = '• Unexpected parser error occurred ({:s})'.format(''.join(e.args))
        else:
            info = ''
    
    if isinstance(remind_parse, datetime):
        remind_parse = remind_parse.replace(tzinfo=display_tz)
        remind_utc = remind_parse.astimezone(tz.UTC)
        remind_at = remind_utc.replace(tzinfo=None)
    elif isinstance(remind_parse, str):
        remind_at = remind_parse
    else:
        remind_at = None  # could be hit in case of error in parser

    return (remind_at, info, None)


def parse(input, utcnow, timezone='UTC'):
    """parse the input string into a datetime object
       this can be either relative or absolute, in relation to the input utcnow
       the function can respect the given timezone, for absolute and semi-absolute dates (e.g. oy)

    Args:
        input (str): input string, provided by the user
        utcnow (datetime): current utc time
        timezone (str, optional): target timezone (tzfile string). Defaults to 'UTC'.

    Raises:
        e: [description]

    Returns:
        (Datetime, str): Datetime: input target, returns utcnow on failure, might return dates in the past, can be None
                         str: info string on why the parser failed/ignored parts of the input
 
        (str, str):      str: rrule of reocurring event, can be None
                         str: info string on why the parser failed/gnored parst of the input
    """
    err = False

    display_tz = tz.gettz(timezone)
    tz_now = utcnow.replace(tzinfo=tz.UTC).astimezone(display_tz) # create local time, used for some parsers
    
    # first split into the different arguments
    # next separate number form char arguments

    rx = re.compile(r'[^a-zA-Z0-9-]') # allow negative sign
    args = rx.split(input)

    args = list(filter(lambda a: a != None and a != '', args))
    args = list(map(_split_arg, args))
    args = _join_spaced_args(args)
    
  
    remind_at, info, ex = _parse_relative(args, utcnow)
    early_abort = (ex != None)

    if remind_at == utcnow and not early_abort:
        remind_at, info_iso, ex = _parse_iso(input, utcnow, display_tz)
        early_abort = (ex != None)
        
        # iso date will only override info on success
        # error is not overriding and only shown when no prev. info is avail.
        if (remind_at != utcnow) or (not info):
            info = info_iso

    if remind_at == utcnow and not early_abort:
        remind_at, info, ex = _parse_fuzzy(input, utcnow, display_tz)
        early_abort = (ex != None)

    # negative intervals are not allowed
    if isinstance(remind_at, datetime) and remind_at < utcnow:
        info += '• the given date must be in the future\n'
        info += '  current utc-time is:  {:s}\n'.format(utcnow.strftime('%Y-%m-%d %H:%M'))
        info += '  interpreted input is: {:s}\n'.format(remind_at.strftime('%Y-%m-%d %H:%M'))
        # return negative intervals, but keep warning
    elif isinstance(remind_at, datetime):
        # protect against out of epoch dates
        try:
            datetime.timestamp(remind_at)  # correct timezones don't matter here
        except OSError:
            info =  '• the given date is exceeding the linux epoch\n'
            info += '  please choose an earlier date'
            return (utcnow, info)

    return (remind_at, info)



def rrule_to_english(rrule, now=None):
    """convert a rrule or rrule string back to an english natural interval
       can aswell suport datetime objects as input

    Args:
        rrule (rrule.rrule or str or datetime.datetime): input argument 
        now (datetime.datetime, optional): current time for parser. Defaults to utcnow()

    Returns:
        [str]: description of inputted interval or date in english
    """
    
    if not now:
        now = datetime.utcnow()

    r = RecurringEvent(now_date=now, preferred_time_range=(0,12), parse_constants=_parse_consts)
    text = r.format(rrule)
    
    return text


def rrule_normalize(rrule_str, dtstart, instance_id=None):
    """generate the rrule of the given rrule string
       if the string contains timezone based offsets (iso dates)
       they are converted into the non-timezone aware utc equivalent

    Args:
        rule_str ([type]): [description]
        dtstart ([type]): [description]

    Returns:
        (rule, str): normalized rule (to utc) None on failure, error string
    """

    try:
        rule = rr.rrulestr(rrule_str)
    except Exception as e:
        return None, str(e)

    until = rule._until
    until_utc = None

    if until:
        # convert the until date to non-tz aware
        until_utc = until.astimezone(tz.UTC)
        until_utc = until_utc.replace(tzinfo=None)

    try:
        rule = rr.rrulestr(rrule_str, dtstart=dtstart, ignoretz=True)
    except Exception as e:
        return None, str(e)

    if until_utc:
        rule = rule.replace(until=until_utc)


    norm_str = str(rule).lower()
    

    if 'minutely' in norm_str:
        return (None, 'Minutely repetitions are not supported by this bot (yet)')
    elif 'secondly' in norm_str:
        return (None, 'Secondly repetitions would be classified as spam by the discord TOS.')
    
    
    # make sure, that the rule is a valid rule
    # sometimes logical errors (like asking for hour 40) can slip through the parser
    # they don't immediately violate the rfc, but are logically not possible to achieve
    
    ruleset = rr.rruleset()
    ruleset.rdate(dtstart)
    ruleset.rrule(rr.rrulestr(norm_str))
    
    try:
        ruleset.after(dtstart)
    except TypeError:
        return (None, f'The rulestring {norm_str} cannot be satisfied')
    
    return rule, None
