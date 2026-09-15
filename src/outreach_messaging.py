"""Template-only drafts: no invented observations or relationships."""
from datetime import timedelta

def follow_up(start, days):
    if type(days) is not int or days<1: raise ValueError('Follow-up business days must be positive')
    date=start
    while days:
        date+=timedelta(days=1)
        if date.weekday()<5: days-=1
    return date.isoformat()

def messaging(row, route):
    name=' '.join(str(row.get('name','')).split())
    greeting=('Hi '+name+' team,') if name else 'Hi there,'
    message=greeting+" I'm Kayla with KidProductionz. I offer branding photography and short-form content for local businesses. Would you be open to a brief conversation about content for your business?"
    if route=='RESEARCH':
        return dict(suggested_opening='',email_subject='',email_body='',dm_draft='',next_action='Verify business identity and a direct contact channel; review routing before outreach.')
    action={'CALL_FIRST':'Confirm business hours and number ownership; review the opening before manually calling.',
            'EMAIL_FIRST':'Verify the email belongs to the business; review the draft before manually sending.',
            'DM_FIRST':'Verify the profile belongs to the business; review the draft before manually sending.'}[route]
    return dict(suggested_opening=message,email_subject='Brand photography and short-form content',email_body=message,dm_draft=message,next_action=action)
