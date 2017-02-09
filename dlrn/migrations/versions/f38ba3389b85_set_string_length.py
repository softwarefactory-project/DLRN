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

"""Set string length

Revision ID: f38ba3389b85
Revises: 1268c799620f
Create Date: 2017-01-12 18:42:25.593667

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f38ba3389b85'
down_revision = '1268c799620f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('project_name', existing_type=sa.String(),
                              type_=sa.String(256))
        batch_op.alter_column('repo_dir', existing_type=sa.String(),
                              type_=sa.String(1024))
        batch_op.alter_column('distgit_dir', existing_type=sa.String(),
                              type_=sa.String(1024))
        batch_op.alter_column('commit_hash', existing_type=sa.String(),
                              type_=sa.String(64))
        batch_op.alter_column('distro_hash', existing_type=sa.String(),
                              type_=sa.String(64))
        batch_op.alter_column('distgit_dir', existing_type=sa.String(),
                              type_=sa.String(1024))
        batch_op.alter_column('commit_branch', existing_type=sa.String(),
                              type_=sa.String(256))
        batch_op.alter_column('status', existing_type=sa.String(),
                              type_=sa.String(64))
        batch_op.alter_column('rpms', existing_type=sa.String(),
                              type_=sa.Text())
        batch_op.alter_column('notes', existing_type=sa.String(),
                              type_=sa.Text())

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column('project_name', existing_type=sa.String(),
                              type_=sa.String(256))


def downgrade():
    with op.batch_alter_table("commits") as batch_op:
        batch_op.alter_column('project_name', existing_type=sa.String(256),
                              type_=sa.String())
        batch_op.alter_column('repo_dir', existing_type=sa.String(1024),
                              type_=sa.String())
        batch_op.alter_column('distgit_dir', existing_type=sa.String(1024),
                              type_=sa.String())
        batch_op.alter_column('commit_hash', existing_type=sa.String(64),
                              type_=sa.String())
        batch_op.alter_column('distro_hash', existing_type=sa.String(64),
                              type_=sa.String())
        batch_op.alter_column('distgit_dir', existing_type=sa.String(1024),
                              type_=sa.String())
        batch_op.alter_column('commit_branch', existing_type=sa.String(256),
                              type_=sa.String())
        batch_op.alter_column('status', existing_type=sa.String(64),
                              type_=sa.String())
        batch_op.alter_column('rpms', existing_type=sa.Text(),
                              type_=sa.String())
        batch_op.alter_column('notes', existing_type=sa.Text(),
                              type_=sa.String())

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column('project_name', existing_type=sa.String(256),
                              type_=sa.String())
