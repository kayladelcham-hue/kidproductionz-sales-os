from __future__ import annotations
import json
import os, json
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, select, update, func, text, delete, inspect
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, Campaign, Prospect, Run, QueueItem, CrmState, Upload, ExternalAction, CalendarEvent, EmailActivity, GoogleConnection, AppSetting, User, UserSession
def _url():
    u=os.getenv('DATABASE_URL','sqlite:///data/kidproductionz.db')
    if u.startswith('postgresql://'): u='postgresql+psycopg://'+u[len('postgresql://'):]
    if not (u.startswith('sqlite:///') or u.startswith('postgresql+psycopg://')): raise RuntimeError(f'Unsupported DATABASE_URL scheme: {u.split(":",1)[0]}')
    return u
DATABASE_URL=_url()
_kw={'connect_args':{'check_same_thread':False}} if DATABASE_URL.startswith('sqlite:///') else {}
engine=create_engine(DATABASE_URL, future=True, **_kw)
SessionLocal=sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
@contextmanager
def session_scope():
    s=SessionLocal()
    try: yield s; s.commit()
    except Exception: s.rollback(); raise
    finally: s.close()
def get_user_by_email(email):
    with SessionLocal() as s:
        user = s.execute(
            select(User).where(User.email == email.strip().lower())
        ).scalar_one_or_none()
        return _dict(user)


def save_user_session(
    token_hash,
    user_id,
    csrf_token_hash=None,
    expires_at=None,
):
    with session_scope() as s:
        session = UserSession(
            token_hash=token_hash,
            user_id=user_id,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
        )
        s.add(session)


def get_user_session(token_hash):
    with SessionLocal() as s:
        session = s.get(UserSession, token_hash)
        return _dict(session)


def delete_user_session(token_hash):
    with session_scope() as s:
        session = s.get(UserSession, token_hash)
        if session:
            s.delete(session)
def connect(): return engine.connect()
def init_db():
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    campaign_columns = {
        column["name"]
        for column in inspector.get_columns("campaign")
    }

    if "owner_id" not in campaign_columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE campaign ADD COLUMN owner_id INTEGER")
            )
def _dict(obj):
    if obj is None:return None
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}
def seed_campaigns(config_dir=None): return 0
def persist_upload(metadata):
    with session_scope() as s: s.merge(Upload(**{k:v for k,v in metadata.items() if k in Upload.__table__.columns.keys()}))
def update_sales_activity(prospect_id,status=None,notes=None,booked_value=None):
    with session_scope() as s:
        p=s.get(Prospect,prospect_id)
        if not p:return None
        if status is not None:p.sales_status=status
        if notes is not None:p.notes=notes
        if booked_value is not None:p.booked_value=booked_value
        return _dict(p)
def move_prospect_queue(prospect_id, queue):
    with session_scope() as s:
        p=s.get(Prospect,prospect_id)
        if not p:return None
        p.queue=queue
        return _dict(p)
def activity_metrics(campaign=None):
    with SessionLocal() as s:
        base_filters = []

        if campaign:
            campaign_id = s.execute(
                select(Campaign.id).where(Campaign.slug == campaign)
            ).scalar_one_or_none()

            if campaign_id is None:
                return {
                    'queue': 0,
                    'attempted_or_contacted': 0,
                    'replies': 0,
                    'consultations_set': 0,
                    'booked': 0,
                    'booked_revenue': 0.0,
                }

            base_filters.append(Prospect.campaign_id == campaign_id)

        status_query = (
            select(Prospect.sales_status, func.count())
            .group_by(Prospect.sales_status)
        )

        if base_filters:
            status_query = status_query.where(*base_filters)

        rows = s.execute(status_query).all()
        counts = {str(k or 'UNKNOWN'): int(v) for k, v in rows}

        revenue_query = select(
            func.coalesce(func.sum(Prospect.booked_value), 0)
        ).where(Prospect.sales_status == 'BOOKED')

        if base_filters:
            revenue_query = revenue_query.where(*base_filters)

        booked_revenue = s.execute(revenue_query).scalar_one()

        queue_query = (
            select(func.count())
            .select_from(Prospect)
            .where(
                Prospect.queue == 'DAILY_QUEUE',
                Prospect.sales_status == 'NOT_CONTACTED'
            )
        )

        if base_filters:
            queue_query = queue_query.where(*base_filters)

        queue_count = s.execute(queue_query).scalar_one()

        return {
            'queue': int(queue_count or 0),
            'attempted_or_contacted': (
                counts.get('ATTEMPTED', 0) +
                counts.get('CONTACTED', 0)
            ),
            'replies': counts.get('REPLIED', 0),
            'consultations_set': counts.get('CONSULTATION_SET', 0),
            'booked': counts.get('BOOKED', 0),
            'booked_revenue': float(booked_revenue or 0),
        }

def ensure_queue_item(item,campaign):
    with session_scope() as s:
        q=s.execute(select(QueueItem).where(QueueItem.run_id==item.get('run_id'),QueueItem.prospect_id==item.get('prospect_id'))).scalar_one_or_none()
        if q:return _dict(q)
        q=QueueItem(**{k:v for k,v in item.items() if k in QueueItem.__table__.columns.keys()}); s.add(q); s.flush(); return _dict(q)
def persist_crm_state(prospect_id,result):
    with session_scope() as s:
        q=s.execute(select(CrmState).where(CrmState.prospect_id==prospect_id)).scalar_one_or_none()
        vals={k:v for k,v in result.items() if k in CrmState.__table__.columns.keys() and k!='id'}; vals['prospect_id']=prospect_id
        if q:
            for k,v in vals.items(): setattr(q,k,v)
        else:s.add(CrmState(**vals))
def get_crm_state(prospect_id):
    with SessionLocal() as s:return _dict(s.execute(select(CrmState).where(CrmState.prospect_id==prospect_id)).scalar_one_or_none())
def log_external_action(prospect_id,action_type,metadata=None):
    with session_scope() as s:s.add(ExternalAction(prospect_id=prospect_id,action_type=action_type,metadata_json=json.dumps(metadata) if metadata is not None else None))
def list_campaigns(owner_id=None):
    with SessionLocal() as s:
        q = select(Campaign).order_by(Campaign.name)
        if owner_id is not None:
            q = q.where(Campaign.owner_id == owner_id)
        return [_dict(x) for x in s.execute(q).scalars()]


def list_prospects(campaign=None, owner_id=None):
    with SessionLocal() as s:
        q = select(Prospect).order_by(Prospect.id)
        if campaign or owner_id is not None:
            q = q.join(Campaign, Prospect.campaign_id == Campaign.id)
        if campaign:
            q = q.where(Campaign.slug == campaign)
        if owner_id is not None:
            q = q.where(Campaign.owner_id == owner_id)
        return [_dict(x) for x in s.execute(q).scalars()]


def get_campaign(slug, owner_id=None):
    with SessionLocal() as s:
        q = select(Campaign).where(Campaign.slug == slug)
        if owner_id is not None:
            q = q.where(Campaign.owner_id == owner_id)
        return _dict(s.execute(q).scalar_one_or_none())


def create_campaign(data, owner_id=None):
    with session_scope() as s:
        values = {
            k: v
            for k, v in data.items()
            if k in Campaign.__table__.columns.keys() and k != 'id'
        }
        if owner_id is not None:
            values['owner_id'] = owner_id
        campaign = Campaign(**values)
        s.add(campaign)
        s.flush()
        return _dict(campaign)


def update_campaign(slug, data, owner_id=None):
    with session_scope() as s:
        q = select(Campaign).where(Campaign.slug == slug)
        if owner_id is not None:
            q = q.where(Campaign.owner_id == owner_id)
        campaign = s.execute(q).scalar_one_or_none()
        if not campaign:
            return None
        for key, value in data.items():
            if key in Campaign.__table__.columns.keys() and key != 'id':
                setattr(campaign, key, value)
        s.flush()
        return _dict(campaign)


def delete_campaign(slug, owner_id=None):
    with session_scope() as s:
        campaign_query = select(Campaign).where(Campaign.slug == slug)
        if owner_id is not None:
            campaign_query = campaign_query.where(Campaign.owner_id == owner_id)
        campaign = s.execute(campaign_query).scalar_one_or_none()

        if not campaign:
            return None

        count_query = select(func.count()).select_from(Campaign)
        if owner_id is not None:
            count_query = count_query.where(Campaign.owner_id == owner_id)
        campaign_count = s.execute(count_query).scalar_one()

        if campaign_count <= 1:
            raise ValueError('At least one campaign is required')

        campaign_id = campaign.id

        prospect_ids = list(
            s.execute(
                select(Prospect.id).where(
                    Prospect.campaign_id == campaign_id
                )
            ).scalars()
        )

        run_ids = list(
            s.execute(
                select(Run.id).where(
                    Run.campaign_id == campaign_id
                )
            ).scalars()
        )

        # Remove records owned through prospects.
        if prospect_ids:
            s.execute(
                delete(EmailActivity).where(
                    EmailActivity.prospect_id.in_(prospect_ids)
                )
            )

            s.execute(
                delete(CalendarEvent).where(
                    CalendarEvent.prospect_id.in_(prospect_ids)
                )
            )

            s.execute(
                delete(ExternalAction).where(
                    ExternalAction.prospect_id.in_(prospect_ids)
                )
            )

            s.execute(
                delete(CrmState).where(
                    CrmState.prospect_id.in_(prospect_ids)
                )
            )

            s.execute(
                delete(QueueItem).where(
                    QueueItem.prospect_id.in_(prospect_ids)
                )
            )

        # Remove queue rows associated with campaign runs.
        if run_ids:
            s.execute(
                delete(QueueItem).where(
                    QueueItem.run_id.in_(run_ids)
                )
            )

        prospects_deleted = len(prospect_ids)
        runs_deleted = len(run_ids)

        s.execute(
            delete(Prospect).where(
                Prospect.campaign_id == campaign_id
            )
        )

        s.execute(
            delete(Run).where(
                Run.campaign_id == campaign_id
            )
        )

        s.delete(campaign)

        return {
            'deleted': True,
            'campaign_id': slug,
            'prospects_deleted': prospects_deleted,
            'runs_deleted': runs_deleted,
        }

def get_settings(prefix=None):
    with SessionLocal() as s:
        q=select(AppSetting)
        if prefix:q=q.where(AppSetting.key.like(prefix+'%'))
        return {x.key:x.value for x in s.execute(q).scalars()}
def save_settings(values):
    with session_scope() as s:
        for k,v in values.items():
            x=s.get(AppSetting,k)
            if x:x.value=str(v)
            else:s.add(AppSetting(key=k,value=str(v)))
def save_google_connection(data):
    with session_scope() as s:
        x=s.get(GoogleConnection,1)
        vals={k:v for k,v in data.items() if k in GoogleConnection.__table__.columns.keys() and k!='id'}
        if x:
            for k,v in vals.items():setattr(x,k,v)
        else:s.add(GoogleConnection(id=1,**vals))
def load_google_connection():
    with SessionLocal() as s:return _dict(s.get(GoogleConnection,1))
def clear_google_connection():
    with session_scope() as s:
        x=s.get(GoogleConnection,1)
        if x:s.delete(x)

def persist_generated_prospects(campaign, items):
    """Persist newly generated prospects safely with conservative deduplication."""

    def norm(value):
        return " ".join(str(value or "").strip().casefold().split())

    def norm_phone(value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def norm_web(value):
        value = str(value or "").strip().casefold()
        for prefix in ("https://", "http://"):
            if value.startswith(prefix):
                value = value[len(prefix):]
        if value.startswith("www."):
            value = value[4:]
        value = value.split("#", 1)[0].split("?", 1)[0]
        return value.rstrip("/")

    def keys_for(row):
        keys = set()

        phone = norm_phone(row.get("phone"))
        website = norm_web(row.get("website"))
        external = norm(
            row.get("place_id")
            or row.get("google_id")
            or row.get("external_key")
        )

        name = norm(row.get("name") or row.get("business"))
        address = norm(row.get("address"))
        city = norm(row.get("city"))
        state = norm(row.get("state"))

        if external:
            keys.add(("external", external))

        if len(phone) >= 7:
            keys.add(("phone", phone))

        if website:
            keys.add(("website", website))

        email = norm(row.get("email"))
        if email:
            keys.add(("email", email))

        if name and address:
            keys.add(("name_address", name, address, city, state))

        # Conservative fallback only when stronger identifiers are absent.
        if (
            name
            and city
            and state
            and not phone
            and not website
            and not address
        ):
            keys.add(("name_city_state", name, city, state))

        return keys

    with session_scope() as s:
        campaign_row = s.execute(
            select(Campaign).where(Campaign.slug == campaign)
        ).scalar_one_or_none()

        # A source-controlled campaign may exist before its database row.
        # Create the DB record lazily from the trusted campaign config so
        # generated prospects always receive a valid numeric campaign_id.
        if not campaign_row:
            config_path = (
                Path(__file__).resolve().parents[2]
                / "config"
                / "campaigns"
                / f"{campaign}.json"
            )

            if not config_path.exists():
                raise KeyError(f"Campaign not found: {campaign}")

            config = json.loads(
                config_path.read_text(encoding="utf-8")
            )

            if config.get("campaign_id") != campaign:
                raise ValueError(
                    f"Campaign config mismatch: {campaign}"
                )

            campaign_row = Campaign(
                slug=campaign,
                name=config.get("name") or campaign,
                market=json.dumps(config.get("market") or {}),
                active=1,
                config_ref=str(
                    Path("config")
                    / "campaigns"
                    / f"{campaign}.json"
                ),
                status="ACTIVE",
            )

            s.add(campaign_row)
            s.flush()

        existing = list(
            s.execute(
                select(Prospect).where(
                    Prospect.campaign_id == campaign_row.id
                )
            ).scalars()
        )

        seen = set()

        for prospect in existing:
            row = _dict(prospect)

            # Support external_key when the current schema contains it.
            if hasattr(prospect, "external_key"):
                row["external_key"] = getattr(
                    prospect,
                    "external_key",
                    None,
                )

            seen.update(keys_for(row))

        inserted = []
        duplicates = []
        rejected = []

        prospect_columns = set(
            Prospect.__table__.columns.keys()
        )

        for item in items:

            queue_status = str(
                item.get("queue_status") or ""
            ).upper()

            # Rejected prospects are reported but do not pollute the CRM.
            if queue_status == "INELIGIBLE":
                rejected.append({
                    "name": item.get("name") or item.get("business"),
                    "reason": item.get("rejection_reasons") or [],
                })
                continue

            item_keys = keys_for(item)

            if item_keys and any(k in seen for k in item_keys):
                duplicates.append(
                    item.get("name")
                    or item.get("business")
                    or "Unknown"
                )
                continue

            name = str(
                item.get("name")
                or item.get("business")
                or ""
            ).strip()

            if not name:
                rejected.append({
                    "name": "",
                    "reason": ["MISSING_BUSINESS_NAME"],
                })
                continue

            review_reasons = item.get("review_reasons") or []

            if isinstance(review_reasons, list):
                research = "; ".join(
                    str(x) for x in review_reasons
                )
            else:
                research = str(review_reasons or "")

            data = {
                "campaign_id": campaign_row.id,
                "name": name,
                "email": item.get("email") or None,
                "phone": item.get("phone") or None,
                "website": item.get("website") or None,
                "social": item.get("social") or None,
                "category": item.get("category") or None,
                "normalized_category": item.get(
                    "normalized_category"
                ) or None,
                "address": item.get("address") or None,
                "city": item.get("city") or None,
                "state": item.get("state") or None,
                "zip": item.get("zip") or None,
                "status": item.get("status") or None,
                "score": item.get("score"),
                "raw_score": item.get("raw_score"),
                "grade": item.get("grade") or None,
                "queue": queue_status or "RESEARCH",
                "ownership": item.get("ownership") or None,
                "research": research or None,
                "sales_status": "NOT_CONTACTED",
            }

            # Save Outscraper's stable Google identifier when schema supports it.
            if "external_key" in prospect_columns:
                external = (
                    item.get("place_id")
                    or item.get("google_id")
                )

                if external:
                    data["external_key"] = (
                        "OUTSCRAPER:" + str(external)
                    )

            data = {
                k: v
                for k, v in data.items()
                if k in prospect_columns
            }

            prospect = Prospect(**data)

            s.add(prospect)
            s.flush()

            inserted.append({
                "id": prospect.id,
                "name": prospect.name,
                "queue": getattr(
                    prospect,
                    "queue",
                    queue_status,
                ),
                "score": getattr(
                    prospect,
                    "score",
                    None,
                ),
            })

            seen.update(item_keys)

        return {
            "campaign": campaign,
            "inserted_count": len(inserted),
            "duplicate_count": len(duplicates),
            "rejected_count": len(rejected),
            "inserted": inserted,
            "duplicates": duplicates,
            "rejected": rejected,
        }

__all__=['engine','SessionLocal','session_scope','Base','init_db','seed_campaigns','persist_upload','update_sales_activity','activity_metrics','ensure_queue_item','persist_crm_state','get_crm_state','log_external_action','connect','list_campaigns','list_prospects','get_campaign','create_campaign','update_campaign','delete_campaign','get_settings','save_settings','save_google_connection','load_google_connection','clear_google_connection']


