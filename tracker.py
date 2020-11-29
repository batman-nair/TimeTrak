from datetime import datetime, timedelta
from abc import ABCMeta, abstractmethod
from pymongo import MongoClient

class TrackerStoreBase(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        self.session_break_delay_ = kwargs.get('session_break_delay', 10.0)  # seconds
    @abstractmethod
    def add_tracked_users(self, guild_id, user_ids):
        return NotImplemented
    @abstractmethod
    def get_tracked_users(self, guild_id):
        return NotImplemented
    @abstractmethod
    def add_user_activities_sample(self, guild_id, user_id, activities, start_time, end_time):
        return NotImplemented
    @abstractmethod
    def get_last_user_activities(self, guild_id, user_id, from_time=None):
        return NotImplemented
    @abstractmethod
    def get_aggregated_user_activities(self, guild_id, user_id, from_time=None):
        return NotImplemented
    @abstractmethod
    def delete_guild_data(self, guild_id):
        return NotImplemented
    
class MongoTrackerStore(TrackerStoreBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        mongo_url = kwargs.get('mongo_url', None)   
        self.client_ = MongoClient(mongo_url)
        self.db_ = self.client_['user_data']
    
    def add_tracked_users(self, guild_id, user_ids):
        user_db = self.db_['tracked_user_ids']
        print(f'DB: Adding tracked users for {guild_id}: {user_ids}')
        user_db.find_one_and_update({'guild_id': str(guild_id)}, {'$push': {'tracked_users': {'$each': [str(user_id) for user_id in user_ids]}}}, upsert=True)

    def get_tracked_users(self, guild_id):
        user_db = self.db_['tracked_user_ids']
        guild_tracker = user_db.find_one({'guild_id': str(guild_id)})
        if not guild_tracker:
            return []
        tracked_users = guild_tracker.get('tracked_users', [])
        return list(set(tracked_users))

    def _setup_empty_user(self, guild_id, user_id):
        guild_db = self.db_[str(guild_id)]
        user_data = guild_db.find_one({'user_id': str(user_id)})
        if user_data:    
            return user_data
        guild_db.insert_one({'user_id':str(user_id), 'ongoing_sessions':[], 'sessions':[]})
        return guild_db.find_one({'user_id': str(user_id)})

    def _update_and_check_is_new_ongoing_session(self, user_data, activity_name, start_time, duration):
        for session in user_data['ongoing_sessions'][:]:
            # Check if session is ongoing
            if activity_name == session['name']:
                session_end_time = session['start_time'] + timedelta(seconds=session['duration'])
                # Continue on going session : update duration
                if session_end_time + timedelta(seconds=self.session_break_delay_) > start_time:
                    session['duration'] += duration
                    return False
                # New session, move last session to sessions list and create new ongoing session
                else:
                    user_data['ongoing_sessions'].remove(session)
                    user_data['sessions'].append(session)
                    return True
        return True

    def _clear_old_ongoing_sessions(self, user_data, end_time):
        for session in user_data['ongoing_sessions'][:]:
            session_end_time = session['start_time'] + timedelta(seconds=session['duration'])
            if session_end_time + timedelta(seconds=self.session_break_delay_) < end_time:
                user_data['ongoing_sessions'].remove(session)
                user_data['sessions'].append(session)

    def _add_new_ongoing_session(self, user_data, activity_name, start_time, duration):
        user_data['ongoing_sessions'].append({'name': activity_name, 'start_time': start_time, 'duration': duration})


    def _add_user_activity_sample(self, user_data, activity_name, start_time, end_time):
        duration = (end_time - start_time).total_seconds()
        if self._update_and_check_is_new_ongoing_session(user_data, activity_name, start_time, duration):
            self._add_new_ongoing_session(user_data, activity_name, start_time, duration)

    def add_user_activities_sample(self, guild_id, user_id, activities, start_time, end_time):
        print(f'DB: Adding user {user_id} sample for {activities} from {start_time} to {end_time}')
        guild_db = self.db_[str(guild_id)]
        user_data = guild_db.find_one({'user_id':str(user_id)})
        if not user_data:
            user_data = self._setup_empty_user(guild_id, user_id)
        
        for activity_name in activities:
            self._add_user_activity_sample(user_data, activity_name ,start_time, end_time)
        self._clear_old_ongoing_sessions(user_data, end_time)
        
        guild_db.find_one_and_update({'user_id':str(user_id)}, {'$set': {
            'ongoing_sessions': user_data['ongoing_sessions'],
            'sessions': user_data['sessions']
            }}, upsert=False)

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
        aggregate_activities_data = guild_db.aggregate([{'$unwind': '$sessions'}, 
        {'$match': match_data}, 
        {'$group': {'_id':'$sessions.name', 'duration': {'$sum': '$sessions.duration'}}}])
        if not aggregate_activities_data.alive:
            return {}
        aggregate_activities_data = list(aggregate_activities_data)
        aggregated_user_activities = self.get_last_user_activities(guild_id, user_id, from_time=from_time)
        for data in aggregate_activities_data:
            aggregated_user_activities[data['_id']] = aggregated_user_activities.get(data['_id'], 0) + data['duration']
        return aggregated_user_activities

    def delete_guild_data(self, guild_id):
        guild_db = self.db_[str(guild_id)]
        guild_db.drop()
        
        user_db = self.db_['tracked_user_ids']
        user_db.delete_one({'guild_id': str(guild_id)})


def testing():
    print('Testing trackers')

    import os
    from dotenv import load_dotenv

    load_dotenv()
    mongo_url = os.getenv('MONGO_URL')
    
    mg = MongoTrackerStore(mongo_url=mongo_url)

    guild_id = 'test_guild'

    mg.delete_guild_data(guild_id)

    mg.add_tracked_users(guild_id, ['user1', 'user2', 'user3'])

    tracked_users = mg.get_tracked_users(guild_id)
    print('tracked_users: ', tracked_users)

    for user_id in tracked_users:
        mg.add_user_activities_sample(guild_id, user_id, ['activity1'], datetime.now()-timedelta(days=2), datetime.now()-timedelta(days=2)+timedelta(seconds=60))
    # continuous activity
    mg.add_user_activities_sample(guild_id, 'user1', ['activity1'], datetime.now()-timedelta(days=2)+timedelta(seconds=60), datetime.now()-timedelta(days=2)+timedelta(seconds=120))
    # new activity
    mg.add_user_activities_sample(guild_id, 'user2', ['activity1'], datetime.now()-timedelta(days=1), datetime.now()-timedelta(days=1)+timedelta(seconds=60))
    # different activity
    mg.add_user_activities_sample(guild_id, 'user3', ['activity2'], datetime.now()-timedelta(days=2)+timedelta(seconds=60), datetime.now()-timedelta(days=2)+timedelta(seconds=120))
    
# aggr = db1.aggregate([{'$unwind':'$sessions'}, {'$match':{'user_id':'12345'}}, {'$group':{'_id':'$user_id', "duration": {'$sum':"$sessions.duration"}} }])
