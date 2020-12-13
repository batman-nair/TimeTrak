import os
import threading
from datetime import datetime, timedelta

import discord
from tracker import MongoTrackerStore
from dotenv import load_dotenv
from bot import TrakBot

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')
UPDATE_TIME = 60.0 # seconds
SESSION_BREAK_DELAY = 10.0
IS_TRACKER_RUNNING = True

tracker_store = MongoTrackerStore(mongo_url=MONGO_URL, session_break_delay=SESSION_BREAK_DELAY)
client = discord.Client(intents=discord.Intents.all())
bot = TrakBot(client, tracker_store, UPDATE_TIME, SESSION_BREAK_DELAY)

@client.event
async def on_ready():
    update_tracker(client)

def update_tracker(client):
    if IS_TRACKER_RUNNING:
        threading.Timer(UPDATE_TIME, update_tracker, [client]).start()

    bot.update_tracker()

def get_relative_activity_data(guild, target_user, message_data):
    try:
        if message_data[1] != "last" and message_data[2] in ['day', 'days', 'hour', 'hours']:
            message_data.insert(1, "last")
        if message_data[1] == "last":
            if message_data[2] == "session":
                return tracker_store.get_last_user_activities(guild.id, target_user.id)
            time_region = timedelta(seconds=0)
            if message_data[2] == "week":
                time_region = timedelta(days=7)
            elif message_data[2] == "day":
                time_region = timedelta(days=1)
            elif message_data[2] == "month":
                time_region = timedelta(days=30)
            elif message_data[2] == "hour":
                time_region = timedelta(hours=1)
            elif message_data[3].startswith("hour"):
                time_region = timedelta(hours=int(message_data[2]))
            elif message_data[3].startswith("day"):
                time_region = timedelta(days=int(message_data[2]))
            from_time = datetime.now() - time_region
            return tracker_store.get_aggregated_user_activities(guild.id, target_user.id, from_time)
    except Exception as e:
        print(f'Error {e} happened when getting relative time data from {message_data}')
        return {}

@client.event
async def on_message(message):
    print('got message')
    if message.author == client.user or message.author.bot:
        return

    if message.content.startswith('-'):
        guild = message.guild
        message_data = message.content[1:].split()
        if not len(message_data):
            return

        if message_data[0] == 'track':
            assert 0, 'Track command deprecated now'
            return
            # TODO: Add blacklist option
            # user_list = set()
            # try:
            #     for mentioned_user in message.mentions:
            #         user_list.add(mentioned_user.id)
            #     if message_data[1] == 'everyone':
            #         user_list = await guild.fetch_members(limit=None).flatten()
            #         user_id_list = [user.id for user in user_list if not user.bot]
            #     tracker_store.add_tracked_users(guild.id, user_id_list)
            # except:
            #     message.channel.send('Give `-track everyone` or `-track ` and mention list of users to be tracked')
            #     print(f'Error extracting data from message {message}')

        elif message_data[0] == 'stats':
            target_user = message.author
            if message.mentions:
                target_user = message.mentions[0]
            print(f'Targetting user {target_user.name} {target_user.id}')
            guild = message.guild
            activity_data = {}

            if len(message_data) > 1 and message_data[1] == "last":
                activity_data = get_relative_activity_data(guild, target_user, message_data)
            else:
                activity_data = tracker_store.get_aggregated_user_activities(guild.id, target_user.id)
            print(f'Got activity data {activity_data}')
            if not activity_data:
                await message.channel.send(f'No play time data available for user {target_user.name}. Maybe your game activity isn\'t visible or you didn\'t play anything')
                return
            reply_string = f'Play times for user {target_user.name}:\n'
            for activity_name, duration in activity_data.items():
                reply_string += activity_name + ": {:0>8}".format(str(timedelta(seconds=round(duration)))) + '\n'

            await message.channel.send(reply_string)

        elif message_data[0] == 'reset':
            if 'Rjn_Kirito' not in message.author.name:
                message.channel.send('I\'m sorry, but you don\'t have the permission to do that... right now anyways')
                return
            target_users = [message.author]
            if message.mentions:
                target_users = message.mentions
            reply_string = f'Resetting tracked data for {", ".join([user.name for user in target_users])}'
            print(reply_string)
            for user in target_users:
                tracker_store.reset_user_data(message.guild.id, user.id)
            await message.channel.send(reply_string)

client.run(TOKEN)

IS_TRACKER_RUNNING = False
print('Run stopped, stopping thread')