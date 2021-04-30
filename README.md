# Remindme Bot

This is the Remindme Bot for discord.


Key features:
* remind yourself after a certain time period
* remind other users after a certain time period

This bot is inspired by the reddit remindme bot and allows similar usage.

[Invite the Bot](https://discord.com/api/oauth2/authorize?client_id=831142367397412874&permissions=68608&scope=bot%20applications.commands)


This bot is a subset of the bigger [ModBot](https://top.gg/bot/602236567574020133)

## Some users cannot use the bot?

Make sure the user has the permission to perform `slash`-commands.
This is a recently introduced discord permission, and can control the access to bot commands.




## Commands

|Commands||
|---|---|
|```remindme <time> <message>```  | reminds you after the given `<time>` period| 
|```remind <user> <time> <message>``` | reminds another user after the given `<time>` period|
|```timezone <string>``` | set the timezone of your server, used for end-of-day calculation, defaults to UTC|




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
		• mi(ns)
	
	you can combine relative intervals like this
		1y 1mo 2 days -5h
	
	dates are supported aswell, you can try different formats
		• 5 jul, 5th july, july 5
		• 23 sept at 3pm or 23 sept at 15:00
		• 2050

	Note: the parser uses day first (1.2.2021 -> 1st January)
	      absolute days do respect the /timezone of the server

	the reminder can occur as much as 1 minute delayed
```


### Examples

```
/remindme 1y Hello future me
/remindme 2years This is a long time
/remindme 2 h drink some water
/remindme eow Buy groceries
/remindme 5 mi Whatever
/remindme 2 aug 3pm Is it hot outside?

/remind @Use 1 mon What's up
/remind @User 24 dec Merry Christmas
/remind @User eoy Happy new year
```

### Note
The correct plural of the time interval does not matter
`/remindme 1 weeks Hey` is just as valid as `/remindme 2 week Ho`


### Github
https://github.com/Mayerch1/RemindmeBot
