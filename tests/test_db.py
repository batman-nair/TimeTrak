import os
import unittest
from datetime import datetime, timedelta

from src.db import MongoDB
from dotenv import load_dotenv

class TestMongoDB(unittest.TestCase):
    TEST_GUILD = 'test_guild'
    def setUp(self):
        load_dotenv()
        mongo_url = os.getenv('MONGO_URL')
        self.mg_ = MongoDB(mongo_url=mongo_url)
        self.mg_.delete_guild_data(self.TEST_GUILD)

    def test_blacklist_functions(self):
        b_multiple_users = ['b_user1', 'b_user2']
        self.mg_.add_blacklisted_users(self.TEST_GUILD, b_multiple_users)
        self.assertTrue(all(b_user in self.mg_.get_blacklisted_users(self.TEST_GUILD) for b_user in b_multiple_users), "Failed to add multiple users")

        b_one_user = ['b_user3']
        self.mg_.add_blacklisted_users(self.TEST_GUILD, b_one_user)
        self.assertTrue('b_user3' in self.mg_.get_blacklisted_users(self.TEST_GUILD), "Failed to add a single user.")

        self.mg_.remove_blacklisted_users(self.TEST_GUILD, b_multiple_users)
        self.assertEqual(self.mg_.get_blacklisted_users(self.TEST_GUILD), ['b_user3'], "Failed to remove multiple users.")

        self.mg_.remove_blacklisted_users(self.TEST_GUILD, b_one_user)
        self.assertFalse(self.mg_.get_blacklisted_users(self.TEST_GUILD), "Failed to remove a single user.")

    def test_single_activity_data(self):
        first_activity_starttime = datetime.now() - timedelta(days=2)
        self.mg_.add_user_activities_sample(self.TEST_GUILD, 'user1', ['activity1'], first_activity_starttime, first_activity_starttime+timedelta(seconds=60))
        all_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user1')
        filtered_activites = self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user1', from_time=first_activity_starttime+timedelta(days=1))
        self.assertEqual(all_activities.get('activity1'), 60, "Adding single activity failed")
        self.assertFalse(filtered_activites, "From time filter for activity query failed")

    def test_separated_activity_data(self):
        first_activity_starttime = datetime.now() - timedelta(days=2)
        self.mg_.add_user_activities_sample(self.TEST_GUILD, 'user2', ['activity1'], first_activity_starttime, first_activity_starttime+timedelta(seconds=60))
        second_activity_startime = first_activity_starttime + timedelta(days=1)
        self.mg_.add_user_activities_sample(
            self.TEST_GUILD, 'user2', ['activity2'],
            second_activity_startime,
            second_activity_startime+timedelta(seconds=60)
        )
        all_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user2')
        new_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user2', from_time=second_activity_startime-timedelta(seconds=1))
        last_activities = self.mg_.get_last_activities(self.TEST_GUILD, 'user2')
        self.assertEqual(all_activities.get('activity1'), 60, "Past activity time not correct.")
        self.assertEqual(all_activities.get('activity2'), 60, "Current activity time not correct.")
        self.assertEqual(new_activities.get('activity2'), 60, "From time filter for activity query failed.")
        self.assertFalse('activity1' in new_activities, "From time filter for activity query failed.")
        self.assertEqual(last_activities.get('activity2'), 60, "Last activity query is not correct.")


    def test_continuous_activity_data(self):
        first_activity_starttime = datetime.now() - timedelta(days=2)
        self.mg_.add_user_activities_sample(self.TEST_GUILD, 'user3', ['activity1'], first_activity_starttime, first_activity_starttime+timedelta(seconds=60))
        self.mg_.add_user_activities_sample(
            self.TEST_GUILD, 'user3', ['activity1'],
            first_activity_starttime+timedelta(seconds=60),
            first_activity_starttime+timedelta(seconds=120)
        )
        all_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user3')
        last_activities = self.mg_.get_last_activities(self.TEST_GUILD, 'user3')
        self.assertEqual(all_activities.get('activity1'), 120, "Continuous activity time not correct.")
        self.assertEqual(last_activities.get('activity1'), 120, "Last activity query is not correct.")


    def test_reset_functions(self):
        user_list = ['user1', 'user2', 'user3']
        first_activity_starttime = datetime.now() - timedelta(days=2)
        for user_id in user_list:
            self.mg_.add_user_activities_sample(self.TEST_GUILD, user_id, ['activity1'], first_activity_starttime, first_activity_starttime+timedelta(seconds=60))

        self.mg_.reset_user_data(self.TEST_GUILD, 'user1')
        self.assertFalse(self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user1'), "Reset user data failed.")

        self.mg_.reset_guild_data(self.TEST_GUILD)
        self.assertFalse(self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user2'), "Reset guild data failed.")
        self.assertFalse(self.mg_.get_aggregated_activities(self.TEST_GUILD, 'user3'), "Reset guild data failed.")

    def test_multi_user_activity_data(self):
        user_list = ['user1', 'user2', 'user3']
        first_activity_starttime = datetime.now() - timedelta(days=2)
        for user_id in user_list:
            self.mg_.add_user_activities_sample(self.TEST_GUILD, user_id, ['activity1'], first_activity_starttime, first_activity_starttime+timedelta(seconds=60))
        second_activity_startime = first_activity_starttime + timedelta(days=1)
        self.mg_.add_user_activities_sample(
            self.TEST_GUILD, 'user2', ['activity2'],
            second_activity_startime,
            second_activity_startime+timedelta(seconds=60)
        )
        self.mg_.add_user_activities_sample(
            self.TEST_GUILD, 'user3', ['activity1'],
            second_activity_startime,
            second_activity_startime+timedelta(seconds=60)
        )
        all_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD)
        new_activities = self.mg_.get_aggregated_activities(self.TEST_GUILD, from_time=second_activity_startime-timedelta(seconds=1))
        last_activities = self.mg_.get_last_activities(self.TEST_GUILD)
        self.assertEqual(all_activities.get('activity1'), 240, "All activity query is not correct")
        self.assertEqual(all_activities.get('activity2'), 60, "All activity query is not correct")
        self.assertEqual(new_activities.get('activity1'), 60, "From time filter for activity query failed.")
        self.assertEqual(new_activities.get('activity2'), 60, "From time filter for activity query failed.")
        self.assertEqual(last_activities.get('activity1'), 120, "Last activity query is not correct.")
        self.assertEqual(last_activities.get('activity2'), 60, "Last activity query is not correct.")


if __name__ == '__main__':
    unittest.main()
