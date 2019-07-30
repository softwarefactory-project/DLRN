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

"""Rename rpms to artifacts

Revision ID: 2d503b5034b7
Revises: 2a0313a8a7d6
Create Date: 2019-04-26 01:06:50.462042

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d503b5034b7'
down_revision = '2a0313a8a7d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('rpms', existing_type=sa.Text(),
                              new_column_name='artifacts')


def downgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('artifacts', existing_type=sa.Text(),
                              new_column_name='rpms')
