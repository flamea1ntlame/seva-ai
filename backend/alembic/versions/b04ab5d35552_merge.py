"""merge

Revision ID: b04ab5d35552
Revises: ('0088659d92be', 'd4f89a1c23ef')
Create Date: 2026-09-27 02:34:27.294415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b04ab5d35552'
down_revision: Union[str, None] = ('0088659d92be', 'd4f89a1c23ef')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
