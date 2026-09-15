import os
from pathlib import Path

def test_database_v2_fresh_sqlite(tmp_path):
    os.environ['DATABASE_URL']=f"sqlite:///{(tmp_path/'db.sqlite').as_posix()}"
    from app.api import database_v2 as d
    d.init_db(); c=d.create_campaign({'slug':'t','name':'Test'}); assert d.get_campaign('t')['name']=='Test'
    d.save_settings({'x':'y'}); assert d.get_settings()['x']=='y'
    d.save_google_connection({'status':'NOT_CONNECTED'}); assert d.load_google_connection()['status']=='NOT_CONNECTED'
