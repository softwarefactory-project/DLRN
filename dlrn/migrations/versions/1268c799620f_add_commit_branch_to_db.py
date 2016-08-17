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

"""Add commit_branch to DB

Revision ID: 1268c799620f
Revises: 47ebe0522809
Create Date: 2016-08-17 12:08:54.246311

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = '1268c799620f'
down_revision = '47ebe0522809'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('commits', sa.Column('commit_branch', sa.String()))
    commits = table('commits',
                    column('id', sa.Integer),
                    column('commit_branch', sa.String))
    # We cannot retrieve the previous commit_branch in any way, let's
    # set it to master
    op.execute(commits.update()
               .where(commits.c.id == commits.c.id)
               .values(commit_branch="master"))


def downgrade():
    op.drop_column('commits', 'commit_branch')
