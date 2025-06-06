"""Actually add contact_tag to QueryHistory

Revision ID: 321aef75ab48
Revises: 408465ef1483
Create Date: 2025-06-01 08:50:47.157759

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '321aef75ab48'
down_revision = '408465ef1483'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('query_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_tag', sa.String(length=32), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('query_history', schema=None) as batch_op:
        batch_op.drop_column('contact_tag')

    # ### end Alembic commands ###
