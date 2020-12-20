import re
from datetime import datetime, timedelta
import humanize

from discord import Message
from bot import TrakBot

class MessageParser():
    def __init__(self, bot: TrakBot, prefix: str='-'):
        self.bot_ = bot
        self.prefix_ = prefix
        self.invalid_message_ = f'Didn\'t understand the command you gave. Try `{self.prefix_}help` to see basic commands or refer my wiki.'

    async def parse(self, message: Message):
        if not message.content.startswith(self.prefix_):
            return
        message_str = message.content[1:].lower()
        if len(message_str) == 0:
            return
        print('Parser: got message:', message_str)
        command_word = message_str.split()[0]
        if command_word == 'stats':
            await self._parse_stats_message(message)
        elif command_word == 'reset':
            await self._parse_reset_message(message)
        elif command_word == 'help':
            await self._parse_help_message(message)
        else:
            await message.channel.send(self.invalid_message_)

    async def _parse_stats_message(self, message: Message):
        message_str = message.content.lower()
        target_user = message.author
        if message.mentions:
            target_user = message.mentions[0]
        print(f'Parser: Getting stats for user {target_user.name} {target_user.id}')
        guild = message.guild
        activity_data = None
        time_region = None

        if re.match(r'.* (this|last) session', message_str):
            activity_data = self.bot_.get_last_user_activity_data(guild.id, target_user.id)
        elif re.match(r'.* (\d+|last) (day|week|hour|minute)', message_str):
            search_res = re.search(r' (\d+|last) (day|week|hour|minute)', message_str)
            time_region = self._get_time_region_from_string(search_res[1], search_res[2])
            activity_data = self.bot_.get_aggregated_user_activity_data(guild.id, target_user.id, from_time = datetime.now() - time_region)
        elif re.match(r'.* (total|full|forever)', message_str):
            activity_data = self.bot_.get_aggregated_user_activity_data(guild.id, target_user.id, from_time=None)
        else:
            time_region = timedelta(days=7)
            activity_data = self.bot_.get_aggregated_user_activity_data(guild.id, target_user.id, from_time = datetime.now() - time_region)

        print(f'Parser: Got activity data for {target_user}: {activity_data} for {time_region}')
        reply_str = self._get_message_from_activity_data(activity_data, target_user.name, time_region)
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
            return f'No play time data available for **{user_name}**. Maybe your game activity isn\'t visible or you didn\'t play anything.'
        time_string = ''
        if time_region:
            time_string = ' from ' + humanize.precisedelta(time_region) + ' ago'
        reply_string = f'> Play times for **{user_name}**{time_string}:\n'
        for activity_name, duration in activity_data.items():
            reply_string += '> **' + activity_name + '**: ' + humanize.precisedelta(timedelta(seconds=round(duration)), minimum_unit='minutes', format='%d') + '\n'
        return reply_string

    async def _parse_reset_message(self, message: Message):
        if 'Rjn_Kirito' not in message.author.name:
            await message.channel.send('I\'m sorry, but you don\'t have the permission to do that... right now anyways')
            return
        target_users = [message.author]
        if message.mentions:
            target_users = message.mentions
        reply_string = f'Resetting tracked data for {", ".join([user.name for user in target_users])}'
        print('Parser:', reply_string)
        for user in target_users:
            self.bot_.reset_user_data(message.guild.id, user.id)
        await message.channel.send(reply_string)

    async def _parse_help_message(self, message: Message):
        stats_help = f'''`{self.prefix_}stats` gives gamewise play time stats. By default the stats for *a week* is shown.
        - Mention a user to get their stats
        - Get total stats with `{self.prefix_}stats total`
        - A specific time frame can be specified in weeks, days, hours or minutes. eg: `{self.prefix_}stats 2 days`
        - Get most recent play time stats with `{self.prefix_}stats last session`.
        '''
        final_help = '\n'.join([stats_help])
        await message.channel.send(final_help)

