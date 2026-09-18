from __future__ import annotations
from sqlalchemy import Integer, Float, Text, String, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Campaign(Base):
    __tablename__='campaign'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str|None] = mapped_column(Text)
    active: Mapped[int] = mapped_column(Integer, nullable=False, server_default='1')
    config_ref: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')
    city: Mapped[str|None] = mapped_column(Text)
    state: Mapped[str|None] = mapped_column(Text)
    category: Mapped[str|None] = mapped_column(Text)
    description: Mapped[str|None] = mapped_column(Text)
    daily_queue_limit: Mapped[int|None] = mapped_column(Integer)
    status: Mapped[str|None] = mapped_column(Text)

class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="ACTIVE")
    is_admin: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="CURRENT_TIMESTAMP"
    )


class UserSession(Base):
    __tablename__ = "user_session"

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    csrf_token_hash: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="CURRENT_TIMESTAMP"
    )

class Prospect(Base):
    __tablename__='prospect'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str|None] = mapped_column(Text)
    phone: Mapped[str|None] = mapped_column(Text)
    website: Mapped[str|None] = mapped_column(Text)
    social: Mapped[str|None] = mapped_column(Text)
    category: Mapped[str|None] = mapped_column(Text)
    normalized_category: Mapped[str|None] = mapped_column(Text)
    address: Mapped[str|None] = mapped_column(Text)
    city: Mapped[str|None] = mapped_column(Text)
    state: Mapped[str|None] = mapped_column(Text)
    zip: Mapped[str|None] = mapped_column(Text)
    status: Mapped[str|None] = mapped_column(Text)
    score: Mapped[float|None] = mapped_column(Float)
    raw_score: Mapped[float|None] = mapped_column(Float)
    grade: Mapped[str|None] = mapped_column(Text)
    queue: Mapped[str|None] = mapped_column(Text)
    ownership: Mapped[str|None] = mapped_column(Text)
    research: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')
    sales_status: Mapped[str] = mapped_column(Text, nullable=False, server_default='NOT_CONTACTED')
    notes: Mapped[str|None] = mapped_column(Text)
    booked_value: Mapped[float|None] = mapped_column(Float)
    last_activity_at: Mapped[str|None] = mapped_column(Text)
    contacted_at: Mapped[str|None] = mapped_column(Text)
    replied_at: Mapped[str|None] = mapped_column(Text)
    consultation_set_at: Mapped[str|None] = mapped_column(Text)
    booked_at: Mapped[str|None] = mapped_column(Text)
    external_key: Mapped[str|None] = mapped_column(Text)

class Run(Base):
    __tablename__='run'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    run_status: Mapped[str|None] = mapped_column(Text)
    dry_run: Mapped[int] = mapped_column(Integer, nullable=False, server_default='1')
    qualified_count: Mapped[int|None] = mapped_column(Integer)
    daily_queue_count: Mapped[int|None] = mapped_column(Integer)
    deferred_count: Mapped[int|None] = mapped_column(Integer)
    research_count: Mapped[int|None] = mapped_column(Integer)
    ineligible_count: Mapped[int|None] = mapped_column(Integer)
    manifest_ref: Mapped[str|None] = mapped_column(Text)
    queue_artifact_ref: Mapped[str|None] = mapped_column(Text)
    started_at: Mapped[str|None] = mapped_column(Text)
    completed_at: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')

class QueueItem(Base):
    __tablename__='queue_item'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prospect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int|None] = mapped_column(Integer)
    priority: Mapped[str|None] = mapped_column(Text)
    queue_type: Mapped[str|None] = mapped_column(Text)
    status: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')

class CrmState(Base):
    __tablename__='crm_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    sync_status: Mapped[str|None] = mapped_column(Text)
    hubspot_contact_id: Mapped[str|None] = mapped_column(Text)
    hubspot_company_id: Mapped[str|None] = mapped_column(Text)
    hubspot_deal_id: Mapped[str|None] = mapped_column(Text)
    association_verified: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    last_synced_at: Mapped[str|None] = mapped_column(Text)
    metadata_json: Mapped[str|None] = mapped_column('metadata', Text)

class Upload(Base):
    __tablename__='upload'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_reference: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sheets: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')
    expires_at: Mapped[str|None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='ACTIVE')

class ExternalAction(Base):
    __tablename__='external_action'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str|None] = mapped_column('metadata', Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')

class CalendarEvent(Base):
    __tablename__='calendar_event'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    calendar_event_id: Mapped[str|None] = mapped_column(Text)
    event_url: Mapped[str|None] = mapped_column(Text)
    consultation_start: Mapped[str|None] = mapped_column(Text)
    consultation_end: Mapped[str|None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')

class EmailActivity(Base):
    __tablename__='email_activity'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str|None] = mapped_column(Text)
    recipient: Mapped[str|None] = mapped_column(Text)
    subject: Mapped[str|None] = mapped_column(Text)
    sent_at: Mapped[str] = mapped_column(Text, nullable=False, server_default='CURRENT_TIMESTAMP')

class GoogleConnection(Base):
    __tablename__='google_connection'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str|None] = mapped_column(Text)
    refresh_token: Mapped[str|None] = mapped_column(Text)
    expires_at: Mapped[float|None] = mapped_column(Float)
    scope: Mapped[str|None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='NOT_CONNECTED')
    __table_args__=(CheckConstraint('id=1'),)

class AppSetting(Base):
    __tablename__='app_setting'
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

__all__=['Base','Campaign','Prospect','Run','QueueItem','CrmState','Upload','ExternalAction','CalendarEvent','EmailActivity','GoogleConnection','AppSetting']

"User",
"UserSession",
