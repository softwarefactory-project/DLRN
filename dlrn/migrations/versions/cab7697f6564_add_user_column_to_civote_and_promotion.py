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

"""Add user column to civote and promotion

Revision ID: cab7697f6564
Revises: 4a5651777e5e
Create Date: 2017-11-24 13:14:05.750269

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cab7697f6564'
down_revision = '4a5651777e5e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('civotes', sa.Column('user', sa.String(256)))
    op.add_column('promotions', sa.Column('user', sa.String(256)))
    # We have no means to know which user created the existing votes/promotions
    # so let's acccept that it can be empty


def downgrade():
    op.drop_column('civotes', 'user')
    op.drop_column('promotions', 'user')
