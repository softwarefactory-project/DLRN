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

"""Add commitrefs table

Revision ID: a5d5eb506c1e
Revises: b6f658f481f8
Create Date: 2019-04-05 14:43:25.832669

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5d5eb506c1e'
down_revision = 'b6f658f481f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('commitrefs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('commit_id', sa.Integer(),
                              sa.ForeignKey('commits.id'),
                              nullable=False),
                    sa.Column('referenced_commit_id', sa.Integer(),
                              sa.ForeignKey('commits.id'),
                              nullable=False),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('commitrefs')
