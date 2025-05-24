"""Force show_journey_publicly default to False"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '57004b85f3ab'
down_revision = '4deccca89a94'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column(
        'users', 
        'show_journey_publicly',
        existing_type=sa.Boolean(),
        server_default=sa.false(),
        existing_nullable=True
    )

def downgrade():
    op.alter_column(
        'users', 
        'show_journey_publicly',
        existing_type=sa.Boolean(),
        server_default=sa.true(),
        existing_nullable=True
    )

