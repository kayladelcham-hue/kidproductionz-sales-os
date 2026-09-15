"""Minimal HubSpot REST adapter for the guarded TEST sync path."""
import json, os, socket, urllib.error, urllib.request
class HubSpotAPIError(RuntimeError):
    def __init__(self,status,operation,details): self.status=status; self.operation=operation; self.details=details; super().__init__(f'HUBSPOT_HTTP_{status}')

class HubSpotClient:
    def __init__(self, token=None, base_url='https://api.hubapi.com', timeout=7):
        self.token=token or os.getenv('HUBSPOT_ACCESS_TOKEN'); self.base_url=base_url.rstrip('/'); self.timeout=max(1,min(float(timeout),10))
        if not self.token: raise ValueError('HUBSPOT_ACCESS_TOKEN is required')
    def _request(self, method, path, payload=None, operation='request'):
        body=json.dumps(payload).encode() if payload is not None else None
        headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','Content-Type':'application/json'}
        req=urllib.request.Request(self.base_url+path,data=body,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r: return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try: details=json.loads(e.read().decode('utf-8'))
            except Exception: details={}
            safe={k:details.get(k) for k in ('status','message','category','correlationId','errors','context') if k in details}
            raise HubSpotAPIError(e.code,operation,safe) from e
        except (TimeoutError, socket.timeout): raise RuntimeError('HUBSPOT_TIMEOUT')
        except urllib.error.URLError as e: raise RuntimeError('HUBSPOT_CONNECTION_ERROR') from e
    def get(self, object_type, object_id): return self._request('GET',f'/crm/v3/objects/{object_type.lower()}s/{object_id}')
    def get_contact(self, contact_id): return self.get('contact',contact_id)
    def get_deal(self, deal_id): return self.get('deal',deal_id)
    def create_contact(self, prospect):
        name=str(prospect.get('name') or prospect.get('business') or '').strip()
        props={k:prospect[k] for k in ('email','phone','website') if prospect.get(k)}
        if name: props['company']=name
        try: return self._request('POST','/crm/v3/objects/contacts',{'properties':props},'contact_create')
        except TypeError: return self._request('POST','/crm/v3/objects/contacts',{'properties':props})
    def create_deal(self, prospect):
        name=str(prospect.get('name') or prospect.get('business') or 'KidProductionz Prospect')
        pipeline=os.getenv('HUBSPOT_PIPELINE_ID'); stage=os.getenv('HUBSPOT_STAGE_ID')
        if not pipeline: raise ValueError('HUBSPOT_PIPELINE_ID is required for configured pipeline KidProductionz Sales Cycle')
        if not stage: raise ValueError('HUBSPOT_STAGE_ID is required for configured stage New Prospect')
        try: return self._request('POST','/crm/v3/objects/deals',{'properties':{'dealname':name,'pipeline':pipeline,'dealstage':stage}},'deal_create')
        except TypeError: return self._request('POST','/crm/v3/objects/deals',{'properties':{'dealname':name,'pipeline':pipeline,'dealstage':stage}})
    def association_exists(self, deal_id, contact_id):
        data=self._request('GET',f'/crm/v4/objects/deals/{deal_id}/associations/contacts')
        return any(str(x.get('toObjectId',x.get('id','')))==str(contact_id) for x in data.get('results',[]))
    def associate(self, deal_id, contact_id):
        # CRM v3 existing-record association uses the directional Deal -> Contact type 3.
        path=f'/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/3'
        try: return self._request('PUT',path,operation='association_create')
        except TypeError: return self._request('PUT',path)
    def verify_association(self, deal_id, contact_id): return self.association_exists(deal_id,contact_id)
