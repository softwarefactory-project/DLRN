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

"""Scheme change due to SCM support moving to a plugin

Revision ID: 47ebe0522809
Revises: o3c62b0d3ec34
Create Date: 2016-06-08 11:29:16.460075

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = '47ebe0522809'
down_revision = '3c62b0d3ec34'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('distgit_dir', sa.String()))
    commits = table('commits',
                    column('id', sa.Integer),
                    column('repo_dir', sa.String),
                    column('distgit_dir', sa.String))
    op.execute(commits.update()
               .where(commits.c.id == commits.c.id)
               .values(distgit_dir=(commits.c.repo_dir + "_distro")))


def downgrade():
    op.drop_column('commits', 'distgit_dir')
