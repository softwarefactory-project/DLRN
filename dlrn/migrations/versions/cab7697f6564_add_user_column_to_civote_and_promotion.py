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
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = 'cab7697f6564'
down_revision = '4a5651777e5e'
branch_labels = None
depends_on = None


def upgrade():
    # We are creating a default user "system", without a valid password
    # This will be used to assign all promotions/CI votes a default user
    users = table('users',
                  column('username', sa.String(256)),
                  column('password', sa.String(256)))

    op.execute(users.insert()
               .values(username='system', password='system'))

    # Since SQLite3 does not allow ALTER TABLE statements, we need to do a
    # batch operation: http://alembic.zzzcomputing.com/en/latest/batch.html
    with op.batch_alter_table('civotes') as batch_op:
        batch_op.add_column(sa.Column('user',
                                      sa.String(256),
                                      sa.ForeignKey('users.username',
                                                    name='civ_user_fk')))
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.add_column(sa.Column('user', sa.String(256),
                            sa.ForeignKey('users.username',
                                          name='prom_user_fk')))

    civotes = table('civotes',
                    column('id', sa.Integer),
                    column('user', sa.String(256)))

    op.execute(civotes.update().values(user='system'))

    promotions = table('promotions',
                       column('id', sa.Integer),
                       column('user', sa.String(256)))

    op.execute(promotions.update().values(user='system'))

    # Set the NOT NULL constraint at the end, otherwise we have a chicken&egg
    # situation while we add the system user to the tables
    with op.batch_alter_table('civotes') as batch_op:
        batch_op.alter_column('user', nullable=False)
    with op.batch_alter_table('promotions') as batch_op:
        batch_op.alter_column('user', nullable=False)


def downgrade():
    with op.batch_alter_table('civotes') as batch_op:
        batch_op.drop_constraint('civ_user_fk', type_='foreignkey')
        batch_op.drop_column('user')

    with op.batch_alter_table('promotions') as batch_op:
        batch_op.drop_constraint('prom_user_fk', type_='foreignkey')
        batch_op.drop_column('user')

    users = table('users',
                  column('username', sa.String(256)),
                  column('password', sa.String(256)))
    op.execute(users.delete().where('username="system"'))
