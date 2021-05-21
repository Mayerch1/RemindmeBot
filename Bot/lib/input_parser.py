import re
import copy
from datetime import datetime, timedelta

import dateutil.parser
from dateutil.relativedelta import *
from dateutil import tz


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

def emoji_to_num(emoji):
    """convert unicode emoji back to integer
    Arguments:
        emoji {str} -- unicode to convert back, only supports single digits
    Returns:
        [int] -- number of emoji, None if emoji was not a number
    """
    if emoji == '1️⃣':
        return 1
    elif emoji == '2️⃣':
        return 2
    elif emoji == '3️⃣':
        return 3
    elif emoji == '4️⃣':
        return 4
    elif emoji == '5️⃣':
        return 5
    elif emoji == '6️⃣':
        return 6
    elif emoji == '7️⃣':
        return 7
    elif emoji == '8️⃣':
        return 8
    elif emoji == '9️⃣':
        return 9
    elif emoji == '0️⃣':
        return 0
    else:
        return None    


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


def _parse_absolute(args, utcnow, now_local):

    total_intvl = timedelta(hours=0)
    error = ''
    info = ''

    for arg in args:
        if arg[1] == 'eoy':
            tmp = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            eoy = tmp + relativedelta(years=1, days=-1)
            total_intvl = eoy - now_local

        elif arg[1] == 'eom':
            tmp = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            eom = tmp + relativedelta(months=1, hours=-12)
            total_intvl = eom - now_local

        elif arg[1] == 'eow':
            w_day = now_local.weekday()
            week_start = now_local - timedelta(days=w_day)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

            eow = week_start + relativedelta(days=5, hours=-1)
            total_intvl = eow - now_local

        elif arg[1] == 'eod':
            tmp = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            eod = tmp + relativedelta(days=1, minutes=-15)
            total_intvl = eod - now_local

        else:
            info = info + f'• ignoring {arg}, as absolute and relative intervals cannot be mixed\n'


    return (total_intvl, info)
            

def _parse_relative(args):

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

            else:
                if arg[1] == 'm':
                    info = info + f'• Ambiguous reference to minutes/months. Please write out at least `mi` for minutes or `mo` for months\n'
                else:
                    info = info + f'• Ignoring {arg}, as this is not a known interval\n'
            
        total_intvl += intvl


    return (total_intvl, info)


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
        (Datetime, str): Datetime: input target, returns utcnow on failure, cannot be in the past
                         str: info string on why the parser failed/ignored parts of the input
    """
    err = False

    
    # first split into the different arguments
    # next separate number form char arguments

    rx = re.compile(r'[^a-zA-Z0-9-]') # allow negative sign
    args = rx.split(input)

    args = list(filter(lambda a: a != None and a != '', args))
    args = list(map(_split_arg, args))
    args = _join_spaced_args(args)
    

    now_local = utcnow.replace(tzinfo=tz.UTC).astimezone(tz.gettz(timezone))

    remind_in, info = _parse_absolute(args, utcnow, now_local)

    if remind_in == timedelta(hours=0):
        remind_in, info = _parse_relative(args)

    # reminder is in utc domain
    
    # special case 'm': this is a valid timeframe for dateutil.parse
    # but its blacklisted on purpose, due to ambiguity to month/minutes of own parser
    if remind_in == timedelta(hours=0) and not re.match(r'-?\d+\W?m', input):
        try:
            remind_parse = dateutil.parser.parse(input, dayfirst=True)
        except dateutil.parser.ParserError as e:
            info = '• ' + ' '.join(e.args)
            remind_parse = None
        except:
            remind_parse = None
            info = '• Unexpected parser error occurred'
        else:
            info = ''


        # convert the given time from timezone to UTC
        # needs to be made tz-aware first
        # the resulting remind_at is not timezone aware again
        if remind_parse:
            remind_parse = remind_parse.replace(tzinfo=tz.gettz(timezone))
            remind_utc = remind_parse.astimezone(tz.UTC)
            remind_at = remind_utc.replace(tzinfo=None)
        else:
            remind_at = utcnow
    else:
        remind_at = utcnow + remind_in

    # negative intervals are not allowed
    if remind_at < utcnow:
        remind_at = utcnow
        info += '• the given date must be in the future\n'
        info += '  current utc-time is:     {:s}\n'.format(utcnow.strftime('%Y-%m-%d %H:%M'))
        info += '  chosen reminder time is: {:s}\n'.format(remind_at.strftime('%Y-%m-%d %H:%M'))

    return (remind_at, info)
