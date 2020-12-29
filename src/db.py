from typing import Optional, List, Dict
from datetime import datetime, timedelta
from abc import ABCMeta, abstractmethod
from pymongo import MongoClient

from .log import Logger

_log = Logger('DB')

class BaseDB(metaclass=ABCMeta):
    def __init__(self, session_break_delay: Optional[float]=10.0, **kwargs):
        self.session_break_delay_ = session_break_delay
        self.debug_ = kwargs.get('debug', False)
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
    def get_last_activities(self, guild_id: int, user_id: Optional[int]=None, from_time: Optional[datetime]=None):
        return NotImplemented
    @abstractmethod
    def get_aggregated_activities(self, guild_id: int, user_id: Optional[int]=None, from_time: Optional[datetime]=None):
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

class MongoDB(BaseDB):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        mongo_url = kwargs.get('mongo_url', None)
        if not mongo_url:
            raise RuntimeError('Mongo URL not specified. Can\'t initialize database.')
        self.client_ = MongoClient(mongo_url)
        self.db_ = self.client_['user_data']

    def add_blacklisted_users(self, guild_id, user_ids):
        user_db = self.db_['blacklisted_user_ids']
        _log.debug(f'Adding blacklisted users for {guild_id}: {user_ids}')
        user_db.find_one_and_update(
            {'guild_id': str(guild_id)},
            {'$push': {'blacklisted_users': {'$each': [str(user_id) for user_id in user_ids]}}},
            upsert=True)

    def remove_blacklisted_users(self, guild_id, user_ids):
        user_db = self.db_['blacklisted_user_ids']
        guild_tracker = user_db.find_one({'guild_id':str(guild_id)})
        if not guild_tracker:
            return False
        _log.debug(f'Removing blacklisted users for {guild_id}: {user_ids}')
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
        _log.debug(f'Adding {guild_id} user {user_id} sample for {activities} from {start_time} to {end_time}')
        if self.debug_:
            return
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

    def get_last_activities(self, guild_id, user_id=None, from_time=None):
        last_activities = self._get_aggregated_field_activites_as_dict('ongoing_sessions', guild_id, user_id, from_time)
        _log.debug(f'user data for {guild_id}, {user_id} {last_activities} {from_time}')
        return last_activities

    def _get_aggregated_field_activites_as_dict(self, field_name: str, guild_id: int, user_id: Optional[int], from_time: Optional[datetime]):
        assert field_name in ['ongoing_sessions', 'sessions'], "Got invalid field name in query"
        guild_db = self.db_[str(guild_id)]
        match_data = dict()
        if user_id:
            match_data['user_id'] = str(user_id)
        if from_time:
            match_data[f'{field_name}.start_time'] = {'$gte': from_time}
        aggregate_activities_data = guild_db.aggregate([
            {'$unwind': f'${field_name}'},
            {'$match': match_data},
            {'$group': {'_id': f'${field_name}.name',
                        'duration': {'$sum': f'${field_name}.duration'}}}
            ])
        _log.debug('Got aggregate activitites for field', field_name, aggregate_activities_data)
        return self._convert_aggregate_data_to_dict(aggregate_activities_data)

    def _convert_aggregate_data_to_dict(self, aggregate_data: List[dict]) -> Dict[str, int]:
        dict_data = dict([(data['_id'], data['duration']) for data in aggregate_data])
        return dict_data

    def get_aggregated_activities(self, guild_id, user_id=None, from_time=None):
        aggregated_activities = self._get_aggregated_field_activites_as_dict('sessions', guild_id, user_id, from_time)
        last_activities = self.get_last_activities(guild_id, user_id, from_time)
        for activity, duration in last_activities.items():
            aggregated_activities[activity] = aggregated_activities.get(activity, 0) + duration
        _log.debug(f'user data for {guild_id}, {user_id} {from_time} {aggregated_activities}')
        return aggregated_activities

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

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()
    mongo_url = os.getenv('MONGO_URL')

    mg = MongoDB(mongo_url=mongo_url)
