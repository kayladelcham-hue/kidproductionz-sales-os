"""Add event-based KP Momentum ledger.

Revision ID: 0004_kp_momentum
Revises: 0003_user_icp_qualification
"""
from alembic import op
import sqlalchemy as sa

revision="0004_kp_momentum"
down_revision="0003_user_icp_qualification"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("momentum_event",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),nullable=False,index=True),sa.Column("prospect_id",sa.Integer(),nullable=True,index=True),sa.Column("event_type",sa.Text(),nullable=False,index=True),sa.Column("points",sa.Integer(),nullable=False),sa.Column("idempotency_key",sa.Text(),nullable=False,unique=True),sa.Column("metadata",sa.Text()),sa.Column("created_at",sa.Text(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP"),index=True))

def downgrade():
    op.drop_table("momentum_event")
