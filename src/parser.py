import re
from datetime import datetime, timedelta
from typing import List, Optional
import humanize

from discord import Message, File, Guild
from .log import Logger
from .bot import TrakBot

_log = Logger('Parser')

class MessageParser():
    def __init__(self, bot: TrakBot, prefix: str='-'):
        self.bot_ = bot
        self.prefix_ = prefix
        self.invalid_message_ = f'Didn\'t understand the command you gave. Try `{self.prefix_}help` to see basic commands or refer my wiki.'

    async def parse(self, message: Message):
        if not re.match(f'{self.prefix_}[a-zA-Z]', message.content):
            return
        message_str = message.content[len(self.prefix_):].lower()
        if len(message_str) == 0:
            return
        _log.debug('got message:', message_str)
        command_word = message_str.split()[0]
        if command_word == 'stats':
            await self._parse_stats_message(message)
        elif command_word == 'server':
            await self._parse_server_message(message)
        elif command_word == 'plot':
            await self._parse_plot_message(message)
        elif command_word == 'longest':
            await self._parse_longest_message(message)
        elif command_word == 'help':
            await self._parse_help_message(message)
        else:
            await message.channel.send(self.invalid_message_)

    async def _parse_stats_message(self, message: Message):
        message_str = message.content.lower()
        target_user = message.author
        if message.mentions:
            target_user = message.mentions[0]
        _log.debug(f'Getting stats for user {target_user.name} {target_user.id}')
        guild = message.guild
        activity_data = None
        time_region = None

        if re.match(r'.* (this|last) session', message_str):
            activity_data = self.bot_.get_last_activity_data(guild.id, target_user.id)
        elif re.match(r'.* (\d+|last) (day|week|hour|minute)', message_str):
            search_res = re.search(r' (\d+|last) (day|week|hour|minute)', message_str)
            time_region = self._get_time_region_from_string(search_res[1], search_res[2])
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, target_user.id, from_time = datetime.now() - time_region)
        elif re.match(r'.* (total|full|forever)', message_str):
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, target_user.id, from_time=None)
        else:
            time_region = timedelta(days=7)
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, target_user.id, from_time = datetime.now() - time_region)

        _log.debug(f'Got activity data for {target_user}: {activity_data} for {time_region}')
        reply_str = self._get_message_from_activity_data(activity_data, target_user.name, time_region)
        await message.channel.send(reply_str)

    def _get_time_region_from_string(self, time_str: str, unit_str: str) -> timedelta:
        num = int(time_str) if time_str.isdigit() else 1
        if unit_str == "day":
            return timedelta(days=num)
        elif unit_str == "week":
            return timedelta(days=7*num)
        elif unit_str == "hour":
            return timedelta(hours=num)
        elif unit_str == "minute":
            return timedelta(minutes=num)

    def _get_message_from_activity_data(self, activity_data: dict, user_name: str, time_region: timedelta=None, max_activities: int=15) -> str:
        if not activity_data:
            return f'No play time data available for **{user_name}**. Maybe your game activity isn\'t visible or you didn\'t play anything.'
        time_string = ''
        if time_region:
            time_string = ' from ' + humanize.precisedelta(time_region) + ' ago'
        reply_string = f'>>> Top play times for **{user_name}**{time_string}:\n\n'
        sorted_activity_data_list = sorted(activity_data.items(), key=lambda el: el[1], reverse=True)
        for activity_name, duration in sorted_activity_data_list[:max_activities]:
            reply_string += '**' + activity_name + '**: ' + humanize.precisedelta(timedelta(seconds=round(duration)), minimum_unit='minutes', format='%d') + '\n'
        return reply_string

    async def _parse_server_message(self, message: Message):
        message_str = message.content.lower()
        guild = message.guild
        _log.debug(f'Getting stats for server {guild.name}')
        activity_data = None
        time_region = None

        if re.match(r'.* (\d+|last) (day|week|hour|minute)', message_str):
            search_res = re.search(r' (\d+|last) (day|week|hour|minute)', message_str)
            time_region = self._get_time_region_from_string(search_res[1], search_res[2])
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, from_time = datetime.now() - time_region)
        elif re.match(r'.* (total|full|forever)', message_str):
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, from_time=None)
        else:
            time_region = timedelta(days=7)
            activity_data = self.bot_.get_aggregated_activity_data(guild.id, from_time = datetime.now() - time_region)

        _log.debug(f'Got activity data for server {guild.name}: {activity_data} for {time_region}')
        reply_str = self._get_message_from_activity_data(activity_data, guild.name, time_region)
        await message.channel.send(reply_str)

    async def _parse_plot_message(self, message: Message):
        message_str = message.content.lower()
        target_user = None
        if message.mentions:
            target_user = message.mentions[0]
        guild = message.guild
        if re.match(r'.* server', message_str):
            target_user = None
        _log.debug(f'Plotting heatmap for {target_user}')
        target_user_id = target_user.id if target_user else None
        target_user_name = target_user.name if target_user else guild.name
        self.bot_.plot_session_weekly_heatmap(guild.id, target_user_id)

        await message.channel.send(content=f'Weekwise playtime heatmap for {target_user_name}', file=File('plot.png'))

    async def _parse_longest_message(self, message: Message):
        message_str = message.content.lower()
        target_user = message.author
        if message.mentions:
            target_user = message.mentions[0]
        if re.match(r'.* server', message_str):
            target_user = None
        guild = message.guild
        _log.debug(f'Getting longest activity data for {target_user}')
        target_user_id = target_user.id if target_user else None
        target_user_name = target_user.name if target_user else None
        longest_activity_data = self.bot_.get_longest_activity_data(guild.id, target_user_id)
        reply_str = self._get_message_from_longest_activites(longest_activity_data, target_user_name, guild)
        await message.channel.send(reply_str)

    def _get_message_from_longest_activites(self, longest_activities: List[dict], target_user: Optional[str], guild: Guild, max_activities: int=10) -> str:
        user_name = target_user if target_user else guild.name
        if not longest_activities:
            return f'No play time data available for **{user_name}**. Maybe your game activity isn\'t visible or you didn\'t play anything.'
        reply_str = f'>>> Longest sessions for {user_name}\n\n'
        for activity in longest_activities[:max_activities]:
            reply_str += '**' + activity['name'] + '**: ' + humanize.precisedelta(timedelta(seconds=round(activity['duration'])), minimum_unit='minutes', format='%d') + '\n'
            reply_str += '- _' + humanize.naturaldate(activity['start_time'])
            if not target_user:
                reply_str += ' by ' + guild.get_member(int(activity['user_id'])).name
            reply_str += '_ \n'
        return reply_str


    async def _parse_help_message(self, message: Message):
        stats_help = f'''`{self.prefix_}stats` gives gamewise play time stats. By default the stats for *a week* is shown.
        - Mention a user to get their stats
        - Get total stats with `{self.prefix_}stats total`
        - A specific time frame can be specified in weeks, days, hours or minutes. eg: `{self.prefix_}stats 2 days`
        - Get most recent play time stats with `{self.prefix_}stats last session`.
        '''
        server_stats_help = f'''`{self.prefix_}server` is similar to stats but for the whole server.
        - Time frames can be specified similar to stats like `{self.prefix_}server total` or `{self.prefix_}server 2 days`
        '''
        plot_help = f'''`{self.prefix_}plot` gives a heatmap of weekwise playtime stats.
        - Mention a user to get their heatmap. By default the server stats is given.
        '''
        longest_help = f'''`{self.prefix_}longest` gives the top 10 longest sessions you had.
        - Mention a user to get their longest sessions.
        - Get longest sessions in the server with `{self.prefix_}longest server`.
        '''
        final_help = '\n'.join([stats_help, server_stats_help, plot_help, longest_help])
        await message.channel.send(final_help)

