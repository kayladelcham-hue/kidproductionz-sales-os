"""Controlled lead rescoring, evidence, and score history.

Revision ID: 0005_controlled_rescoring
Revises: 0004_kp_momentum
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_controlled_rescoring"
down_revision = "0004_kp_momentum"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prospect", sa.Column("last_scored_at", sa.Text(), nullable=True))
    op.add_column("prospect", sa.Column("last_enriched_at", sa.Text(), nullable=True))
    op.create_table(
        "lead_signal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prospect_id", sa.Integer(), nullable=False, index=True),
        sa.Column("signal_type", sa.Text(), nullable=False, index=True),
        sa.Column("signal_value", sa.Text(), nullable=False),
        sa.Column("polarity", sa.Text(), nullable=False, server_default="POSITIVE"),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_verified_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "lead_score_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prospect_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("previous_score", sa.Float()),
        sa.Column("new_score", sa.Float(), nullable=False),
        sa.Column("score_delta", sa.Float(), nullable=False),
        sa.Column("icp_version", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("enrichment_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("explanation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), index=True),
    )


def downgrade():
    op.drop_table("lead_score_history")
    op.drop_table("lead_signal")
    op.drop_column("prospect", "last_enriched_at")
    op.drop_column("prospect", "last_scored_at")
