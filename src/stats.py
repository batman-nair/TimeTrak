from typing import Optional
from datetime import datetime, timedelta
import math
import numpy as np
import matplotlib.pyplot as plt

from .log import Logger
from .db import BaseDB, IdType

_log = Logger('Stats')

class StatsGenerator():
    def __init__(self, db: BaseDB):
        self.db_ = db

    def plot_session_heatmap(self, guild_id: IdType, user_id: Optional[IdType] = None, file_name: str = 'plot.png'):
        sessions_data = self.db_.get_raw_sessions_data(guild_id, user_id)
        # sessions_data = [{'start_time': datetime(2020, 1, 1, 0, 0, 0, 0), 'duration': 3600*14}]
        data_samples = []
        for session in sessions_data:
            start_timestamp = session['start_time'] + timedelta(hours=5, minutes=30)
            duration_left = session['duration']
            while duration_left > 0:
                next_timestamp = start_timestamp.replace(second=math.floor(
                    start_timestamp.second/1800)*1800, microsecond=0) + timedelta(seconds=1800)
                iter_duration = min(
                    duration_left, (next_timestamp - start_timestamp).total_seconds())
                data_samples.append((
                    start_timestamp.isoweekday(),
                    start_timestamp.hour*2 + math.floor(start_timestamp.minute/30),
                    iter_duration))
                duration_left -= iter_duration
                start_timestamp = next_timestamp
        xx_weekday = [sample[0] for sample in data_samples]
        yy_hours = [sample[1] for sample in data_samples]
        weights = [sample[2]/60 for sample in data_samples]
        _log.debug('Plotting ', data_samples)
        plt.clf()
        plt.hist2d(xx_weekday, yy_hours, bins=[
                   np.arange(-0.5, 8, 1), np.arange(24*2+1)], weights=weights, cmap='Blues')
        plt.xticks(list(range(1, 8)), [
                   'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        plt.yticks(list(range(0, 24*2+1, 2)), list(range(25)))
        plt.xlim(0.5, 7.5)
        plt.ylabel('Hour')
        plt.xlabel('Weekday')
        cb = plt.colorbar()
        cb.set_label('Minutes of playtime')
        plt.savefig(file_name)
        pass

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from .db import MongoDB
    load_dotenv()
    mongo_url = os.getenv('MONGO_URL')
    mg = MongoDB(mongo_url=mongo_url)

    st = StatsGenerator(mg)
