"""Request-local integration settings; never mutate process-wide credentials."""
from contextvars import ContextVar
import os

user_id = ContextVar('kp_user_id', default=0)
is_admin = ContextVar('kp_is_admin', default=False)
active = ContextVar('kp_request_active', default=False)

def setting(key, default=''):
    owner = user_id.get()
    if owner or active.get():
        from .database_v2 import get_settings
        saved = get_settings(f'user:{owner}:integration:')
        value = saved.get(f'user:{owner}:integration:{key}')
        if value is not None:
            return value
        # Existing environment credentials remain available only to the admin.
        if owner and not is_admin.get() and key.startswith(('HUBSPOT_', 'OUTSCRAPER_')):
            return default
    return os.getenv(key, default)

def save_integration_settings(values):
    from .database_v2 import save_settings
    prefix = f'user:{user_id.get()}:integration:'
    save_settings({prefix + key: str(value) for key, value in values.items()})
