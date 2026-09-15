import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)
FIX = Path(__file__).parent / 'fixtures' / 'v5_inputs'

def test_csv_upload_and_preview():
    data = (FIX / 'valid_orlando.csv').read_bytes()
    r = client.post('/api/campaigns/upload', files={'file': ('leads.csv', data, 'text/csv')})
    assert r.status_code == 200
    body = r.json(); assert body['file_type'] == 'csv' and body['reference']
    p = client.post('/api/campaigns/run-preview', json={'campaign':'orlando_beauty','input_file':body['reference'],'dry_run':True})
    assert p.status_code == 200 and p.json()['input_source'] == body['reference']

def test_xlsx_single_and_multi_sheet_upload():
    for name, sheets in [('campaign_single_sheet.xlsx',['Businesses']), ('campaign_multi_sheet.xlsx',['Businesses','Notes'])]:
        r = client.post('/api/campaigns/upload', files={'file': (name, (FIX/name).read_bytes(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert r.status_code == 200 and r.json()['sheets'] == sheets

def test_upload_rejections_and_safe_reference():
    assert client.post('/api/campaigns/upload', files={'file': ('x.txt', b'x')}).status_code == 415
    assert client.post('/api/campaigns/upload', files={'file': ('x.csv', b'')}).status_code == 400
    assert client.post('/api/campaigns/upload', files={'file': ('bad.xlsx', (FIX/'invalid_workbook.xlsx').read_bytes())}).status_code == 422

def test_execution_disabled():
    r = client.post('/api/campaigns/run', json={'campaign':'orlando_beauty','input_file':'x.csv','dry_run':True,'confirmed':True})
    assert r.status_code == 403
