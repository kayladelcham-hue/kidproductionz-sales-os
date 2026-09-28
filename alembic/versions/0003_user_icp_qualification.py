"""Add user ICP profiles, qualification snapshots, and lead feedback.

Revision ID: 0003_user_icp_qualification
Revises: 0002_contact_lifecycle_and_deals
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_user_icp_qualification"
down_revision = "0002_contact_lifecycle_and_deals"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("icp_profile", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("user_id",sa.Integer(),nullable=False,unique=True,index=True), sa.Column("profile_json",sa.Text(),nullable=False), sa.Column("weights_json",sa.Text(),nullable=False), sa.Column("version",sa.Integer(),nullable=False,server_default="1"), sa.Column("completed",sa.Integer(),nullable=False,server_default="0"), sa.Column("created_at",sa.Text(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at",sa.Text(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.add_column("prospect",sa.Column("icp_score",sa.Float(),nullable=True))
    op.add_column("prospect",sa.Column("icp_priority",sa.Text(),nullable=True))
    op.add_column("prospect",sa.Column("icp_version",sa.Integer(),nullable=True))
    op.add_column("prospect",sa.Column("qualification_json",sa.Text(),nullable=True))
    op.create_table("lead_feedback", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("prospect_id",sa.Integer(),nullable=False,index=True), sa.Column("user_id",sa.Integer(),nullable=False,index=True), sa.Column("verdict",sa.Text()), sa.Column("outcome",sa.Text()), sa.Column("note",sa.Text()), sa.Column("score_at_feedback",sa.Float()), sa.Column("created_at",sa.Text(),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))

def downgrade():
    op.drop_table("lead_feedback")
    for column in ("qualification_json","icp_version","icp_priority","icp_score"):op.drop_column("prospect",column)
    op.drop_table("icp_profile")
