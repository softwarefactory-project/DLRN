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

"""Extra tables for votes on aggregates

Revision ID: 7fbd3a18502f
Revises: 00a31f1f39c0
Create Date: 2020-01-16 15:22:32.090726

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fbd3a18502f'
down_revision = '00a31f1f39c0'
branch_labels = None
depends_on = None


def upgrade():
    # Since SQLite3 does not allow ALTER TABLE statements, we need to do a
    # batch operation: http://alembic.zzzcomputing.com/en/latest/batch.html
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.add_column(sa.Column('aggregate_hash', sa.String(64),
                                      nullable=True))

    op.create_table('civotes_agg',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('ref_hash', sa.String(64), nullable=False),
                    sa.Column('ci_name', sa.String(256), nullable=True),
                    sa.Column('ci_url', sa.String(1024), nullable=True),
                    sa.Column('ci_vote', sa.Boolean(), nullable=True),
                    sa.Column('ci_in_progress', sa.Boolean(), nullable=True),
                    sa.Column('timestamp', sa.Integer(), nullable=True),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.Column('user', sa.String(255),
                              sa.ForeignKey('users.username')),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('civotes_agg')
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.drop_column('aggregate_hash')
