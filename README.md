![# Remindme Bot](https://discords.com/bots/api/bot/831142367397412874/widget)

This bot is inspired by the reddit remindme bot and allows similar usage.

* Create as many Reminders as you want (no rate limit or vote bounties)
* Create intervals (shortest interval is hourly)
* Remind other users and roles (@everyone)
* Create complex repeating patterns (ics-rrules, rfc-5545)
* Set the timezone of your server
* Minimal Permissions required


<img src="https://imgur.com/YE9qXOE.gif" alt="Create Reminder">


<img src="https://imgur.com/lQrUmkF.gif" alt="Create Interval"/>

---

[Invite the Bot](https://discord.com/api/oauth2/authorize?client_id=831142367397412874&permissions=274877991936&scope=bot%20applications.commands) or view it's profile on [top.gg](https://top.gg/bot/831142367397412874)


## Some users cannot use the bot?


### Permissions
Make sure the user has sufficient permission to execute **Application Commands** (`slash-commands` in earlier versions).
This permission can be used to restrict access to bots, but is usually enabled for @everyone by default

<img src="https://imgur.com/3BGMlVl.png" alt="Create Reminder">

### User Settings
If the permissions are all set, but certain users are still not able to use slash-commands, the discord application might be setup incorrectly. Tell the affected user(s) to open their `user settings` and navigate to the `Text & images` section.

In the lower part of said settings page, you can find an option to toggle the usage of slash-commands.
<img src="https://imgur.com/lI5QRoT.png" alt="Create Reminder">



Make sure the user has the permission to `Use Application commands`.
This is a recently introduced discord permission, and can control the access to bot commands.
By default `@everyone` is allowed to use `slash`-commands.


## Create Repeating intervals

There's two ways of setting interval reminders. Through natural language, or by directly inputting `rrules` based on `rfc5545`.

### Natural Language

Create a reminder with `/remindme` or `/remind` and specify the interval as natural language when setting the `time` argument.
This could be e.g. `every week` or `first monday each month` or `every friday at 20`.

### Inputting Rules

Create a "normal" interval with `/remindme` or `/remind` and set the `time` argument to be the first occurrence of your repeating event.
You can then press the `Set Interval` button to add repeating rules for the event.

The bot supports the full `rfc5545`-spec and allows the combination of up to 25 independent rules to define your custom repeating patterns and to add exception rules.

## Commands

|Commands||
|---|---|
|```remindme <time> <message>```  | reminds you after the given `<time>` period| 
|```remind <mentionable> <time> <message>``` | reminds another user/role after the given `<time>` period|
|```reminder_list``` | manage all your reminders for this server (interactive DM) |
|```settings timezone <string>``` | set the timezone of your server, used for absolute times, defaults to UTC|
|```settings menu``` | show some application settings, to modify the behavior of the bot|


### Examples

```
/remindme 1y Hello future me
/remindme 2years This is a long time
/remindme 2 h drink some water
/remindme eow Buy groceries
/remindme 5 m Whatever
/remindme 2 aug 3pm Is it hot outside?
/remindme 2021-09-02T12:25:00+02:00 iso is cool

/remind @User 1 mon What's up
/remind @Role 24 dec Merry Christmas
/remind @everyone eoy Happy new year

/remindme every friday at 20:15 do stuff
/remind @User every year at 1st july happy birthday
```

## Time parsing

The time parser allows multiple formats for specifying the reminder period.

At the moment, different parameters cannot be combined.

```
	allowed absolutes are
		• eoy - remind at end of year
		• eom - remind at end of month
		• eow - remind at end of working week (Friday night)
		• eod - remind at end of day
	
	allowed intervals are
		• y(ears)
		• mo(nths)
		• w(eeks)
		• d(ays)
		• h(ours)
		• m(ins)
	
	you can combine relative intervals like this
		1y 1mo 2 days -5h

	iso-timestamps are supported
		be aware that specifying a timezone will ignore the server timezone
	
	dates are supported, you can try different formats
		• 5 jul, 5th july, july 5
		• 23 sept at 3pm, 23 sept at 15:00
		• 2030

	Note: the parser uses day-first and year-least
	      (01/02/03 -> 1st February 2003)

	the reminder can occur as much as 1 minute delayed
```


### Note
The correct plural of the time interval does not matter
`/remindme 1 weeks Hey` is just as valid as `/remindme 2 week Ho`


### Github
https://github.com/Mayerch1/RemindmeBot
