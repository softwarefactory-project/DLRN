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

"""Add extended_hash and dt_extended columns to commit table

Revision ID: ade85b2396bc
Revises: cab7697f6564
Create Date: 2018-05-23 12:20:39.199017

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = 'ade85b2396bc'
down_revision = 'cab7697f6564'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('extended_hash', sa.String(64)))
    op.add_column('commits', sa.Column('dt_extended', sa.Integer))
    commits = table('commits',
                    column('id', sa.Integer),
                    column('dt_extended', sa.Integer))
    # For existing commits, set dt_extended to 0 (extended_hash is None)
    op.execute(commits.update()
               .where(commits.c.id == commits.c.id)
               .values(dt_extended=0))


def downgrade():
    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_column('extended_hash')
        batch_op.drop_column('dt_extended')
