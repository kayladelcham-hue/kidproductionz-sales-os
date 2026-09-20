"""Add contact lifecycle and multi-opportunity support without copying contacts."""
from alembic import op
import sqlalchemy as sa

revision = '0002_lifecycle_deals'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('prospect')}
    additions = (
        ('company', sa.Column('company', sa.Text(), nullable=True)),
        ('lifecycle_stage', sa.Column('lifecycle_stage', sa.Text(), nullable=False, server_default='PROSPECT')),
        ('lead_source', sa.Column('lead_source', sa.Text(), nullable=True)),
        ('customer_since', sa.Column('customer_since', sa.Text(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column('prospect', column)
    if 'deal' not in inspector.get_table_names():
        op.create_table(
            'deal',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('prospect_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.Text(), nullable=False),
            sa.Column('stage', sa.Text(), nullable=False, server_default='NEW_LEAD'),
            sa.Column('status', sa.Text(), nullable=False, server_default='ACTIVE'),
            sa.Column('deal_value', sa.Float(), nullable=True),
            sa.Column('revenue_collected', sa.Float(), nullable=False, server_default='0'),
            sa.Column('expected_close', sa.Text(), nullable=True),
            sa.Column('next_action', sa.Text(), nullable=True),
            sa.Column('next_action_at', sa.Text(), nullable=True),
            sa.Column('lost_reason', sa.Text(), nullable=True),
            sa.Column('opened_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('closed_at', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_deal_prospect_id', 'deal', ['prospect_id'])
    op.execute("""
        UPDATE prospect SET lifecycle_stage = CASE
          WHEN sales_status = 'BOOKED' THEN 'CUSTOMER'
          WHEN sales_status IN ('REPLIED', 'CONSULTATION_SET') THEN 'LEAD'
          ELSE 'PROSPECT' END
    """)
    op.execute("""
        UPDATE prospect
        SET customer_since = COALESCE(booked_at, last_activity_at, updated_at, created_at)
        WHERE lifecycle_stage = 'CUSTOMER'
    """)
    op.execute("""
        INSERT INTO deal (
          prospect_id, name, stage, status, deal_value, revenue_collected, closed_at
        )
        SELECT id,
               COALESCE(company, name) || ' Opportunity',
               CASE WHEN lifecycle_stage = 'CUSTOMER' THEN 'WON'
                    WHEN sales_status = 'CONSULTATION_SET' THEN 'CONSULTATION'
                    ELSE 'NEW_LEAD' END,
               CASE WHEN lifecycle_stage = 'CUSTOMER' THEN 'WON' ELSE 'ACTIVE' END,
               booked_value,
               0,
               CASE WHEN lifecycle_stage = 'CUSTOMER' THEN booked_at ELSE NULL END
        FROM prospect
        WHERE lifecycle_stage IN ('LEAD', 'CUSTOMER')
          AND NOT EXISTS (SELECT 1 FROM deal WHERE deal.prospect_id = prospect.id)
    """)


def downgrade():
    # Downgrade intentionally leaves contact data intact until the deal table is removed.
    op.drop_index('ix_deal_prospect_id', table_name='deal')
    op.drop_table('deal')
    op.drop_column('prospect', 'customer_since')
    op.drop_column('prospect', 'lead_source')
    op.drop_column('prospect', 'lifecycle_stage')
    op.drop_column('prospect', 'company')
