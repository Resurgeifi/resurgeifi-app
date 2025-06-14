"""Add hero_name to QueryHistory

Revision ID: c91627c5f13c
Revises: a8e286ab339c
Create Date: 2025-06-13 10:57:15.099498

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c91627c5f13c'
down_revision = 'a8e286ab339c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('query_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hero_name', sa.String(length=50), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('query_history', schema=None) as batch_op:
        batch_op.drop_column('hero_name')

    # ### end Alembic commands ###
