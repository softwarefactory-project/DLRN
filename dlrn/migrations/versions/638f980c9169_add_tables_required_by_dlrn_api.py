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

"""Add tables required by DLRN API

Revision ID: 638f980c9169
Revises: f38ba3389b85
Create Date: 2016-11-22 12:43:21.363066

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '638f980c9169'
down_revision = 'f38ba3389b85'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
                    sa.Column('username', sa.String(256), nullable=False),
                    sa.Column('password', sa.String(256), nullable=False),
                    sa.PrimaryKeyConstraint('username'))

    op.create_table('civotes',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('commit_id', sa.Integer(),
                              sa.ForeignKey('commits.id'),
                              nullable=False),
                    sa.Column('ci_name', sa.String(256), nullable=True),
                    sa.Column('ci_url', sa.String(1024), nullable=True),
                    sa.Column('ci_vote', sa.Boolean(), nullable=True),
                    sa.Column('ci_in_progress', sa.Boolean(), nullable=True),
                    sa.Column('timestamp', sa.Integer(), nullable=True),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('users')
    op.drop_table('civotes')
