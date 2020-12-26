import os
import sys
import threading
from datetime import datetime, timedelta

import discord
from src.tracker import MongoTrackerStore
from dotenv import load_dotenv
from src.bot import TrakBot
from src.parser import MessageParser

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')
UPDATE_TIME = 60.0 # seconds
SESSION_BREAK_DELAY = 10.0
IS_TRACKER_RUNNING = True
DEBUG = len(sys.argv) > 1 and sys.argv[1] == 'debug'

tracker_store = MongoTrackerStore(mongo_url=MONGO_URL, session_break_delay=SESSION_BREAK_DELAY, debug=DEBUG)
client = discord.Client(intents=discord.Intents.all())
bot = TrakBot(client, tracker_store, UPDATE_TIME, SESSION_BREAK_DELAY)
parser = MessageParser(bot, prefix='-' if not DEBUG else '--')

@client.event
async def on_ready():
    update_tracker(client)

def update_tracker(client):
    if IS_TRACKER_RUNNING:
        threading.Timer(UPDATE_TIME, update_tracker, [client]).start()
    bot.update_tracker()

@client.event
async def on_message(message):
    print('got message')
    if message.author == client.user or message.author.bot:
        return
    await parser.parse(message)

client.run(TOKEN)

IS_TRACKER_RUNNING = False
print('Run stopped, stopping thread')