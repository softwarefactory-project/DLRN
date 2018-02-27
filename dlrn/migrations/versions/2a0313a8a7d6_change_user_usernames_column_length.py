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

"""change user/usernames column length

Revision ID: 2a0313a8a7d6
Revises: cab7697f6564
Create Date: 2018-02-27 15:35:04.667089

"""

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '2a0313a8a7d6'
down_revision = 'cab7697f6564'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(256),
                              type_=sa.String(255))

    with op.batch_alter_table("civotes") as batch_op:
        batch_op.alter_column('user', existing_type=sa.String(256),
                              type_=sa.String(255))

    with op.batch_alter_table("promotions") as batch_op:
        batch_op.alter_column('user', existing_type=sa.String(256),
                              type_=sa.String(255))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(255),
                              type_=sa.String(256))

    with op.batch_alter_table("civotes") as batch_op:
        batch_op.alter_column('user', existing_type=sa.String(255),
                              type_=sa.String(256))

    with op.batch_alter_table("promotions") as batch_op:
        batch_op.alter_column('user', existing_type=sa.String(255),
                              type_=sa.String(256))
