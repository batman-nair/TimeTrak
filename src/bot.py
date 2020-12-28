from datetime import datetime, timedelta

import discord
from .log import Logger
from .tracker import BaseDB

_log = Logger('TrakBot')

class TrakBot():
    def __init__(self, client: discord.Client, tracker_store: BaseDB, update_time: int, session_break_delay: int = 10):
        self.client_ = client
        self.tracker_store_ = tracker_store
        self.update_time_ = update_time
        self.session_break_delay_ = session_break_delay
        self.guild_to_tracked_users_ = {}
        self.guild_user_to_current_activities_ = {}

    def update_tracker(self):
        current_time = datetime.now()
        self._check_data_structures()
        _log.info(f'Updating tracker {current_time}')
        for guild in self.client_.guilds:
            for user_id in self.guild_to_tracked_users_[str(guild.id)]:
                self._update_tracker_for_user(guild, int(user_id), current_time)

    def _check_data_structures(self):
        for guild in self.client_.guilds:
            guild_id = str(guild.id)
            if guild_id not in self.guild_to_tracked_users_:
                self.guild_to_tracked_users_[guild_id] = set()
                self.guild_user_to_current_activities_[guild_id] = dict()
            all_users = [str(user.id) for user in guild.members if not user.bot]
            blacklisted_users = self.tracker_store_.get_blacklisted_users(guild_id)
            tracked_users = list(filter(lambda user_id: user_id not in blacklisted_users, all_users))
            self.guild_to_tracked_users_[guild_id].update(tracked_users)
            for tracked_user in tracked_users:
                if tracked_user not in self.guild_user_to_current_activities_[guild_id]:
                    self.guild_user_to_current_activities_[guild_id][str(tracked_user)] = dict()

    def _update_tracker_for_user(self, guild: discord.Guild, user_id: str, current_time: datetime=datetime.now()):
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
            self.tracker_store_.add_user_activities_sample(guild.id, user.id, continued_activites, prev_start_time, current_time)
        ongoing_activities.clear()
        for activity_name in updated_activities:
            ongoing_activities[activity_name] = current_time

    def get_aggregated_user_activity_data(self, guild_id: int, user_id: int, from_time: datetime=None):
        return self.tracker_store_.get_aggregated_user_activities(guild_id, user_id, from_time)

    def get_last_user_activity_data(self, guild_id: int, user_id: int):
        return self.tracker_store_.get_last_user_activities(guild_id, user_id)

    def reset_user_data(self, guild_id: int, user_id: int):
        self.tracker_store_.reset_user_data(guild_id, user_id)

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from .tracker import MongoDB
    import asyncio
    load_dotenv()
    discord_token = os.getenv('DISCORD_TOKEN')
    mongo_url = os.getenv('MONGO_URL')
    tracker_store = MongoDB(mongo_url=mongo_url, debug=True)
    client = discord.Client(intents=discord.Intents.all())
    _log.info('Do a Ctrl-c to get out of the start loop after some time so data is updated')
    client.run(discord_token)
    bot = TrakBot(client, tracker_store, 60)
