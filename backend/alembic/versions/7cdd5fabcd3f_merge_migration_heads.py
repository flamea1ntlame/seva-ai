"""merge migration heads

Revision ID: 7cdd5fabcd3f
Revises: ('6cfbc105b59c', 'b04ab5d35552')
Create Date: 2026-09-27 07:11:21.978827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cdd5fabcd3f'
down_revision: Union[str, None] = ('6cfbc105b59c', 'b04ab5d35552')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
