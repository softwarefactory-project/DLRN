# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Add component to promotions

Revision ID: 7bed5ff86925
Revises: f84aca0549fd
Create Date: 2019-09-27 14:33:21.479735

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = '7bed5ff86925'
down_revision = 'f84aca0549fd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.add_column(sa.Column('component', sa.String(64)))

    promotions = table('promotions',
                       column('id', sa.Integer),
                       column('component', sa.String))
    # For existing promotions, set component to None
    op.execute(promotions.update()
               .where(promotions.c.id == promotions.c.id)
               .values(component=None))


def downgrade():
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.drop_column('component')
