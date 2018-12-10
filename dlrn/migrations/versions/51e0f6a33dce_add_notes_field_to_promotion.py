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

"""Add notes field to Promotion

Revision ID: 51e0f6a33dce
Revises: 2a0313a8a7d6
Create Date: 2018-12-10 15:56:47.349967

"""

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '51e0f6a33dce'
down_revision = '2a0313a8a7d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.add_column(sa.Column('notes', sa.String(256)))

def downgrade():
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.drop_column('notes')
