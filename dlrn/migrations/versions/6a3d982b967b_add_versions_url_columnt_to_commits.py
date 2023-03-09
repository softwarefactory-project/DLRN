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

"""Add versions_url columnt to commits

Revision ID: 6a3d982b967b
Revises: 837138eb7daa
Create Date: 2023-01-18 14:05:54.175709

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6a3d982b967b'
down_revision = '837138eb7daa'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('versions_csv', sa.String(256)))


def downgrade():
    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_column('versions_csv')
