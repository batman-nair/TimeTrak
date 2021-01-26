# TimeTrak
Similar to StatTrak for CS:GO but for playtimes via discord. 
[Add the bot to your server and test it out.](https://discord.com/api/oauth2/authorize?client_id=780416332399116298&permissions=0&scope=bot)

Once the bot is added, it'll automatically start collecting playtime data. Get the commands for the bot below. 

## Why a bot for this?
To have a unified way to get playtime info of the games you played and others are playing. Some stats like number of hours played in a week or time played on your last session are just cool to know. 

If you have games on multiple platforms - Steam, Epic, Origin, Xbox etc, you'll have to open the different apps to get your playtime info. And usually, the platforms will only have info on the total number of hours you played. Discord is something I always have open regardless of the game, so that was a common point for data.

## Commands
`-stats` gives gamewise play time stats. By default the stats for a week is shown.
  - Mention a user to get their stats
  - Get stats from forever with `-stats total` or `-stats forever`
  - A specific time frame can be specified in weeks, days, hours or minutes. eg: `-stats 2 days`
  - Get most recent play time stats with `-stats last session`

`-server` is similar to stats but for the whole server.
  - Time frames can be specified similar to stats like `-server total` or `-server 2 days`

`-plot` gives a heatmap of weekwise playtime stats.
  - Mention a user to get their heatmap. By default the server stats is given.
  
`-longest` gives the top 10 longest sessions you had.
  - Mention a user to get their longest sessions.
  - Get longest sessions in the server with `-longest server`.
  
`-help` prints out this list of commands if you ever need them.

## How it works?
The bot polls the Game Activity data for all the users in the server every minute. Continuous activity is grouped to sessions and stored in a database. The bot is hosted on Heroku with MongoDB Atlas as the database.

## How to run on your own?
First you need to setup tokens `DISCORD_TOKEN` and `MONGO_URL` and set these values in a `.env` file. [Get DISCORD_TOKEN by creating a Discord bot](https://discordpy.readthedocs.io/en/latest/discord.html). MONGO_URL is the connection string to a MongoDB cluster. [Here's how to setup a MongoDB cluster](https://docs.atlas.mongodb.com/getting-started).

1. Setup python environment and install required packages with [pipenv](https://pypi.org/project/pipenv/). `pipenv install; pipenv shell`
2. Start the discord bot with `python main.py`. To run in a debug mode without writing anything to db - `python main.py debug`

### Tests
There are unit tests for db functionality with python's unittest library. `python -m unittest discover` to run all tests.  
I couldn't find a way to test discord based functionality, so there isn't tests on that. _shrug_

## Contributing
Raise an issue or feel free to contribute if you wish to see a new feature or want to add something. Thanks!


_Social image source: arcade PNG Designed By Graphicart from <a href="https://pngtree.com/">Pngtree.com</a>_
