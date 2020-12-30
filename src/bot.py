from datetime import datetime, timedelta
from typing import Optional, Dict

import discord
from .log import Logger
from .db import BaseDB, IdType
from .stats import StatsGenerator

_log = Logger('TrakBot')

class TrakBot():
    def __init__(self, client: discord.Client, db: BaseDB, update_time: int, session_break_delay: int = 10):
        self.client_ = client
        self.db_ = db
        self.update_time_ = update_time
        self.session_break_delay_ = session_break_delay
        self.guild_to_tracked_users_ = {}
        self.guild_user_to_current_activities_ = {}
        self.stats_gen_ = StatsGenerator(db)

    def update_tracker(self):
        current_time = datetime.now()
        self._check_data_structures()
        _log.info(f'Updating tracker {current_time}')
        for guild in self.client_.guilds:
            for user_id in self.guild_to_tracked_users_[str(guild.id)]:
                self._update_tracker_for_user(guild, user_id, current_time)

    def _check_data_structures(self):
        for guild in self.client_.guilds:
            guild_id = str(guild.id)
            if guild_id not in self.guild_to_tracked_users_:
                self.guild_to_tracked_users_[guild_id] = set()
                self.guild_user_to_current_activities_[guild_id] = dict()
            all_users = [str(user.id) for user in guild.members if not user.bot]
            blacklisted_users = self.db_.get_blacklisted_users(guild_id)
            tracked_users = list(filter(lambda user_id: user_id not in blacklisted_users, all_users))
            self.guild_to_tracked_users_[guild_id].update(tracked_users)
            for tracked_user in tracked_users:
                if tracked_user not in self.guild_user_to_current_activities_[guild_id]:
                    self.guild_user_to_current_activities_[guild_id][str(tracked_user)] = dict()

    def _update_tracker_for_user(self, guild: discord.Guild, user_id: IdType, current_time: datetime=datetime.now()):
        user = guild.get_member(int(user_id))
        if not user:
            _log.warning(f'User {user_id} not found in {guild.name}')
            return
        user_activities = [activity.name for activity in user.activities if activity.type == discord.ActivityType.playing]
        if user_activities:
            _log.debug(f'Updating data for user {user} doing {user_activities}')
        ongoing_activities = self.guild_user_to_current_activities_[str(guild.id)][str(user.id)]
        updated_activities = []
        continued_activites = []
        for activity_name in user_activities:
            prev_start_time = ongoing_activities.get(activity_name, None)
            if prev_start_time and prev_start_time + timedelta(seconds=self.update_time_+self.session_break_delay_) > current_time:
                continued_activites.append(activity_name)
            updated_activities.append(activity_name)

        if continued_activites:
            self.db_.add_user_activities_sample(guild.id, user.id, continued_activites, prev_start_time, current_time)
        ongoing_activities.clear()
        for activity_name in updated_activities:
            ongoing_activities[activity_name] = current_time

    def get_aggregated_activity_data(self, guild_id: IdType, user_id: Optional[IdType]=None, from_time: Optional[datetime]=None) -> Dict[str, float]:
        return self.db_.get_aggregated_activities(guild_id, user_id, from_time)

    def get_last_activity_data(self, guild_id: IdType, user_id: IdType) -> Dict[str, float]:
        return self.db_.get_last_activities(guild_id, user_id)

    def reset_user_data(self, guild_id: IdType, user_id: IdType):
        self.db_.reset_user_data(guild_id, user_id)

    def plot_session_weekly_heatmap(self, guild_id: IdType, user_id: Optional[IdType] = None, file_name: str = 'plot.png'):
        self.stats_gen_.plot_session_heatmap(guild_id, user_id, file_name)

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from .db import MongoDB
    import asyncio
    load_dotenv()
    discord_token = os.getenv('DISCORD_TOKEN')
    mongo_url = os.getenv('MONGO_URL')
    db = MongoDB(mongo_url=mongo_url, debug=True)
    client = discord.Client(intents=discord.Intents.all())
    _log.info('Do a Ctrl-c to get out of the start loop after some time so data is updated')
    client.run(discord_token)
    bot = TrakBot(client, db, 60)
