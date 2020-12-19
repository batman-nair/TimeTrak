import re
from datetime import datetime, timedelta
import humanize

from discord import Message
from bot import TrakBot

class MessageParser():
    INVALID_MESSAGE = 'Didn\'t understand the command you gave. Try -help to see basic commands or refer my wiki.'
    def __init__(self, bot: TrakBot, prefix: str='-'):
        self.bot_ = bot
        self.prefix_ = prefix

    async def parse(self, message: Message):
        if not message.content.startswith(self.prefix_):
            return
        message_str = message.content[1:]
        if len(message_str) == 0:
            return
        command_word = message_str.split()[0]
        if command_word == 'stats':
            self._parse_stats_message(message)
        elif command_word == 'reset':
            self._parse_reset_message(message)
        else:
            await message.channel.send(self.INVALID_MESSAGE)

    async def _parse_stats_message(self, message: Message):
        message_str = message.content.lower()
        target_user = message.author
        if message.mentions:
            target_user = message.mentions[0]
        print(f'Getting stats for user {target_user.name} {target_user.id}')
        guild = message.guild
        activity_data = None
        time_region = None

        if len(message_str.split()) == 1:
            activity_data = self.bot_.get_user_activity_data(guild.id, target_user.id, from_time=None)
        elif re.match(r'.* (this|last) session', message_str):
            activity_data = self.bot_.get_last_user_activity_data(guild.id, target_user.id)
        elif re.match(r'.* (\d+|last) (day|week|hour|minute)', message_str):
            search_res = re.search(r' (\d+|last) (day|week|hour|minute)', message_str)
            time_region = self._get_time_region_from_string(search_res[0], search_res[1])
            activity_data = self.bot_.get_last_user_activity_data(guild.id, target_user.id, from_time = datetime.now() - time_region)
        else:
            await message.channel.send(self.INVALID_MESSAGE)
            return

        print(f'Parser: Got activity data for {target_user}: {activity_data}')
        reply_str = self._get_message_from_activity_data(activity_data, message)
        await message.channel.send(reply_str)

    def _get_time_region_from_string(self, time_str: str, unit_str: str):
        num = int(time_str) if time_str.isdigit() else 1
        if unit_str == "day":
            return timedelta(days=num)
        elif unit_str == "week":
            return timedelta(days=7*num)
        elif unit_str == "hour":
            return timedelta(hours=num)
        elif unit_str == "minute":
            return timedelta(minutes=num)

    def _get_message_from_activity_data(self, activity_data: dict, user_name: str, time_region: timedelta=None):
        if not activity_data:
            return f'No play time data available for {user_name}. Maybe your game activity isn\'t visible or you didn\'t play anything.'
        time_string = ''
        if time_region:
            time_string = ' from ' + humanize.precisedelta(time_region) + ' ago'
        reply_string = f'Play times for {user_name}{time_string}:\n'
        for activity_name, duration in activity_data.items():
            reply_string += activity_name + ': ' + humanize.precisedelta(timedelta(seconds=round(duration))) + '\n'
        return reply_string

    async def _parse_reset_message(self, message: Message):
        if 'Rjn_Kirito' not in message.author.name:
            message.channel.send('I\'m sorry, but you don\'t have the permission to do that... right now anyways')
            return
        target_users = [message.author]
        if message.mentions:
            target_users = message.mentions
        reply_string = f'Resetting tracked data for {", ".join([user.name for user in target_users])}'
        print('Parser:', reply_string)
        for user in target_users:
            self.bot_.reset_user_data(message.guild.id, user.id)
        await message.channel.send(reply_string)

