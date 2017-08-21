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

"""Add promotions table

Revision ID: 4a5651777e5e
Revises: 638f980c9169
Create Date: 2017-08-21 11:09:46.349973

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a5651777e5e'
down_revision = '638f980c9169'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('promotions',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('commit_id', sa.Integer(),
                              sa.ForeignKey('commits.id'),
                              nullable=False),
                    sa.Column('promotion_name', sa.String(256),
                              nullable=False),
                    sa.Column('timestamp', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('promotions')
