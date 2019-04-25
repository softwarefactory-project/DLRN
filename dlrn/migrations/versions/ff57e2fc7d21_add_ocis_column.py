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

"""empty message

Revision ID: ff57e2fc7d21
Revises: 2a0313a8a7d6
Create Date: 2019-04-25 07:07:52.212133

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff57e2fc7d21'
down_revision = '2a0313a8a7d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('ocis', sa.Text))


def downgrade():
    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_column('ocis')
