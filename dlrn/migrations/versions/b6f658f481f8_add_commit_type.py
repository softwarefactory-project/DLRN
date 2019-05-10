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

"""Add type column

Revision ID: b6f658f481f8
Revises: 2d503b5034b7
Create Date: 2019-04-26 07:29:09.071710

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = 'b6f658f481f8'
down_revision = '2d503b5034b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commits", sa.Column("type", sa.String(18)))
    commits = table('commits', column('type', sa.String(18)))
    op.execute(commits.update().values(type="rpm"))


def downgrade():
    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_column('type')
