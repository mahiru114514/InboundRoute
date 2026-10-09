from datetime import datetime, timedelta, timezone

SHANGHAI = timezone(timedelta(hours=8))


def at(day, time):
    return int(datetime.fromisoformat(f'{day}T{time}').replace(tzinfo=SHANGHAI).timestamp())


def trip(pacing='balanced', interests=None):
    return {
        'trip_id': 'trip_example', 'version': 3,
        'user_profile': {'pacing': pacing, 'interests': interests or [], 'party_composition': 'solo'},
        'anchor_hotel': {'coordinate': {'lat': 31.23, 'lng': 121.47, 'crs': 'WGS84'}},
        'anchor_arrival': {'at': at('2026-10-04', '08:00'), 'activity_start_at': at('2026-10-04', '09:30'),
                           'coordinate': {'lat': 31.23, 'lng': 121.47, 'crs': 'WGS84'}},
        'anchor_departure': {'at': at('2026-10-08', '18:00'), 'hub_buffer_minutes': 180,
                             'coordinate': {'lat': 31.23, 'lng': 121.47, 'crs': 'WGS84'}},
        'days': [{'day_index': i + 1, 'date': f'2026-10-{i + 4:02}', 'daily_start_local': '09:00',
                  'day_status': 'empty', 'ordered_stops': []} for i in range(5)]}


def poi(number, category='history_culture', lng=121.47, dwell=60):
    return {'poi_id': f'sh_poi_{number:05}', 'names': {'zh-Hans': f'景点{number}'},
            'category': {'level1': category, 'level2': 'museum'},
            'coordinate': {'lat': 31.23, 'lng': lng, 'crs': 'WGS84'},
            'operating_rules': {'closure_data_status': 'verified', 'is_enclosed_attraction': True,
                                'closure_rules': [], 'opening_hours': [{'open': '09:00', 'close': '22:00'}],
                                'dwell_time': {'kind': 'point', 'minutes': dwell}}}
