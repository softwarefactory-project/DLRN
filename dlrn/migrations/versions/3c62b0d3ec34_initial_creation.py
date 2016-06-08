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

"""Initial creation

Revision ID: 3c62b0d3ec34
Revises:
Create Date: 2016-06-17 10:35:54.703517

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c62b0d3ec34'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table('commits',
                        sa.Column('id', sa.Integer(), nullable=False),
                        sa.Column('dt_commit', sa.Integer(), nullable=True),
                        sa.Column('dt_distro', sa.Integer(), nullable=True),
                        sa.Column('dt_build', sa.Integer(), nullable=True),
                        sa.Column('project_name', sa.String(), nullable=True),
                        sa.Column('repo_dir', sa.String(), nullable=True),
                        sa.Column('commit_hash', sa.String(), nullable=True),
                        sa.Column('distro_hash', sa.String(), nullable=True),
                        sa.Column('status', sa.String(), nullable=True),
                        sa.Column('rpms', sa.String(), nullable=True),
                        sa.Column('notes', sa.String(), nullable=True),
                        sa.Column('flags', sa.Integer(), nullable=True),
                        sa.PrimaryKeyConstraint('id'))
        op.create_table('projects',
                        sa.Column('id', sa.Integer(), nullable=False),
                        sa.Column('project_name', sa.String(), nullable=True),
                        sa.Column('last_email', sa.Integer(), nullable=True),
                        sa.PrimaryKeyConstraint('id'))
    except Exception:
        # this means that's a legacy table unversioned by alembic
        pass


def downgrade():
    op.drop_table('projects')
    op.drop_table('commits')
