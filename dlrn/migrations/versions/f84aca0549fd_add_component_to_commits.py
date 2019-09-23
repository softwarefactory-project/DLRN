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

"""Add component to commits

Revision ID: f84aca0549fd
Revises: b6f658f481f8
Create Date: 2019-09-24 11:46:13.682176

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = 'f84aca0549fd'
down_revision = 'b6f658f481f8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('component', sa.String(64)))
    commits = table('commits',
                    column('id', sa.Integer),
                    column('component', sa.String))
    # For existing commits, set component to None
    op.execute(commits.update()
               .where(commits.c.id == commits.c.id)
               .values(component=None))


def downgrade():
    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_column('component')
