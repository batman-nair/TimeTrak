from typing import Optional
from datetime import datetime, timedelta
from abc import ABCMeta, abstractmethod
from pymongo import MongoClient

class TrackerStoreBase(metaclass=ABCMeta):
    def __init__(self, session_break_delay: Optional[float]=10.0, **kwargs):
        self.session_break_delay_ = session_break_delay
    @abstractmethod
    def add_blacklisted_users(self, guild_id: int, user_ids: list):
        return NotImplemented
    @abstractmethod
    def remove_blacklisted_users(self, guild_id: int, user_ids: list):
        return NotImplemented
    @abstractmethod
    def get_blacklisted_users(self, guild_id: int):
        return NotImplemented
    @abstractmethod
    def add_user_activities_sample(self, guild_id: int, user_id: int, activities: list, start_time: datetime, end_time: datetime):
        return NotImplemented
    @abstractmethod
    def get_last_user_activities(self, guild_id: int, user_id: int, from_time: Optional[datetime]=None):
        return NotImplemented
    @abstractmethod
    def get_aggregated_user_activities(self, guild_id: int, user_id: int, from_time: Optional[datetime]=None):
        return NotImplemented
    @abstractmethod
    def reset_guild_data(self, guild_id: int):
        return NotImplemented
    @abstractmethod
    def delete_guild_data(self, guild_id: int):
        return NotImplemented
    @abstractmethod
    def reset_user_data(self, guild_id: int, user_id: int):
        return NotImplemented
    @abstractmethod
    def delete_user_data(self, guild_id: int, user_id: int):
        return NotImplemented

class MongoTrackerStore(TrackerStoreBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        mongo_url = kwargs.get('mongo_url', None)
        self.client_ = MongoClient(mongo_url)
        self.db_ = self.client_['user_data']

    def add_blacklisted_users(self, guild_id, user_ids):
        user_db = self.db_['blacklisted_user_ids']
        print(f'DB: Adding blacklisted users for {guild_id}: {user_ids}')
        user_db.find_one_and_update(
            {'guild_id': str(guild_id)},
            {'$push': {'blacklisted_users': {'$each': [str(user_id) for user_id in user_ids]}}},
            upsert=True)

    def remove_blacklisted_users(self, guild_id, user_ids):
        user_db = self.db_['blacklisted_user_ids']
        guild_tracker = user_db.find_one({'guild_id':str(guild_id)})
        if not guild_tracker:
            return False
        print(f'DB: Removing blacklisted users for {guild_id}: {user_ids}')
        user_ids_str = list(map(str, user_ids))
        blacklisted_users = guild_tracker['blacklisted_users']
        blacklisted_users[:] = list(filter(lambda user_id: user_id not in user_ids_str, blacklisted_users))
        user_db.find_one_and_update(
            {'guild_id':str(guild_id)},
            {'$set': {'blacklisted_users': guild_tracker['blacklisted_users']}},
            upsert=False)

    def get_blacklisted_users(self, guild_id):
        user_db = self.db_['blacklisted_user_ids']
        guild_tracker = user_db.find_one({'guild_id': str(guild_id)})
        if not guild_tracker:
            return []
        blacklisted_users = guild_tracker.get('blacklisted_users', [])
        return list(set(blacklisted_users))

    def add_user_activities_sample(self, guild_id, user_id, activities, start_time, end_time):
        print(f'DB: Adding user {user_id} sample for {activities} from {start_time} to {end_time}')
        guild_db = self.db_[str(guild_id)]
        user_data = guild_db.find_one({'user_id':str(user_id)})
        if not user_data:
            user_data = self._setup_empty_user(guild_id, user_id)

        for activity_name in activities:
            self._add_user_activity_sample(user_data, activity_name ,start_time, end_time)
        self._clear_old_ongoing_sessions(user_data, end_time)

        guild_db.find_one_and_update(
            {'user_id':str(user_id)},
            {'$set': {
                'ongoing_sessions': user_data['ongoing_sessions'],
                'sessions': user_data['sessions']
            }}, upsert=False)

    def _setup_empty_user(self, guild_id, user_id):
        guild_db = self.db_[str(guild_id)]
        user_data = guild_db.find_one({'user_id': str(user_id)})
        if user_data:
            return user_data
        guild_db.insert_one({'user_id':str(user_id), 'ongoing_sessions':[], 'sessions':[]})
        return guild_db.find_one({'user_id': str(user_id)})

    def _add_user_activity_sample(self, user_data, activity_name, start_time, end_time):
        duration = (end_time - start_time).total_seconds()
        if self._update_and_check_is_new_ongoing_session(user_data, activity_name, start_time, duration):
            self._add_new_ongoing_session(user_data, activity_name, start_time, duration)

    def _update_and_check_is_new_ongoing_session(self, user_data, activity_name, start_time, duration):
        for session in user_data['ongoing_sessions'][:]:
            if activity_name == session['name']:
                session_end_time = session['start_time'] + timedelta(seconds=session['duration'])
                if session_end_time + timedelta(seconds=self.session_break_delay_) > start_time:
                    session['duration'] += duration
                    return False
                else:
                    user_data['ongoing_sessions'].remove(session)
                    user_data['sessions'].append(session)
                    return True
        return True

    def _add_new_ongoing_session(self, user_data, activity_name, start_time, duration):
        user_data['ongoing_sessions'].append({'name': activity_name, 'start_time': start_time, 'duration': duration})

    def _clear_old_ongoing_sessions(self, user_data, end_time):
        for session in user_data['ongoing_sessions'][:]:
            session_end_time = session['start_time'] + timedelta(seconds=session['duration'])
            if session_end_time + timedelta(seconds=self.session_break_delay_) < end_time:
                user_data['ongoing_sessions'].remove(session)
                user_data['sessions'].append(session)

    def get_last_user_activities(self, guild_id, user_id, from_time=None):
        guild_db = self.db_[str(guild_id)]
        user_data = guild_db.find_one({'user_id':str(user_id)})
        if not user_data:
            return {}
        last_user_activities = dict()
        for activity_data in user_data['ongoing_sessions']:
            if from_time and from_time > activity_data['start_time']:
                continue
            last_user_activities[activity_data['name']] = activity_data['duration']
        return last_user_activities

    def get_aggregated_user_activities(self, guild_id, user_id, from_time=None):
        guild_db = self.db_[str(guild_id)]
        match_data = {'user_id':str(user_id)}
        if from_time:
            match_data['sessions.start_time'] = {'$gt':from_time}
        aggregate_activities_data = guild_db.aggregate([
            {'$unwind': '$sessions'},
            {'$match': match_data},
            {'$group': {'_id':'$sessions.name', 'duration': {'$sum': '$sessions.duration'}}}
            ])
        aggregate_activities_data = list(aggregate_activities_data)
        aggregated_user_activities = self.get_last_user_activities(guild_id, user_id, from_time=from_time)
        for data in aggregate_activities_data:
            aggregated_user_activities[data['_id']] = aggregated_user_activities.get(data['_id'], 0) + data['duration']
        return aggregated_user_activities

    def reset_guild_data(self, guild_id):
        guild_db = self.db_[str(guild_id)]
        guild_db.drop()

    def delete_guild_data(self, guild_id):
        self.reset_guild_data(guild_id)
        user_db = self.db_['blacklisted_user_ids']
        user_db.delete_one({'guild_id': str(guild_id)})

    def reset_user_data(self, guild_id, user_id):
        guild_db = self.db_[str(guild_id)]
        guild_db.delete_one({'user_id':str(user_id)})

    def delete_user_data(self, guild_id, user_id):
        self.reset_user_data(guild_id, user_id)
        user_db = self.db_['blacklisted_user_ids']
        guild_tracker = user_db.find_one({'guild_id':str(guild_id)})
        guild_tracker['blacklisted_users'][:] = [user_id for user_id in guild_tracker['blacklisted_users'][:] if user_id != str(user_id)]
        user_db.find_one_and_update(
            {'guild_id':str(guild_id)},
            {'$set': {'blacklisted_users': guild_tracker['blacklisted_users']}},
            upsert=False)


# TODO: Unit testing
# def testing():
#     print('Testing trackers')

#     import os
#     from dotenv import load_dotenv

#     load_dotenv()
#     mongo_url = os.getenv('MONGO_URL')

#     mg = MongoTrackerStore(mongo_url=mongo_url)

#     guild_id = 'test_guild'

#     mg.delete_guild_data(guild_id)

#     mg.add_tracked_users(guild_id, ['user1', 'user2', 'user3'])

#     tracked_users = mg.get_tracked_users(guild_id)
#     print('tracked_users: ', tracked_users)

#     for user_id in tracked_users:
#         mg.add_user_activities_sample(guild_id, user_id, ['activity1'], datetime.now()-timedelta(days=2), datetime.now()-timedelta(days=2)+timedelta(seconds=60))
#     # continuous activity
#     mg.add_user_activities_sample(guild_id, 'user1', ['activity1'], datetime.now()-timedelta(days=2)+timedelta(seconds=60), datetime.now()-timedelta(days=2)+timedelta(seconds=120))
#     # new activity
#     mg.add_user_activities_sample(guild_id, 'user2', ['activity1'], datetime.now()-timedelta(days=1), datetime.now()-timedelta(days=1)+timedelta(seconds=60))
#     # different activity
#     mg.add_user_activities_sample(guild_id, 'user3', ['activity2'], datetime.now()-timedelta(days=2)+timedelta(seconds=60), datetime.now()-timedelta(days=2)+timedelta(seconds=120))

#     # Better testing will be added
#     if round(mg.get_last_user_activities(guild_id, 'user3')['activity1']) != 120:
#         print('TEST ERROR')
