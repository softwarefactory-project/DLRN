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

"""Extend extended_hash to 128 chars

Revision ID: 837138eb7daa
Revises: 7fbd3a18502f
Create Date: 2020-11-10 14:51:30.395443

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '837138eb7daa'
down_revision = '7fbd3a18502f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('extended_hash', existing_type=sa.String(64),
                              type_=sa.String(128))


def downgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('extended_hash', existing_type=sa.String(128),
                              type_=sa.String(64))
