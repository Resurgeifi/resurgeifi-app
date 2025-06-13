from datetime import datetime
from pytz import timezone as tz, utc

def get_user_local_bounds(user):
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    user_tz = tz(user.timezone or "UTC")
    local_now = now_utc.astimezone(user_tz)
    start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = local_now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start_of_day.astimezone(utc), end_of_day.astimezone(utc)
