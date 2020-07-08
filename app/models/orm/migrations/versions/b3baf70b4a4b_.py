"""empty message.

Revision ID: b3baf70b4a4b
Revises: b6660d01ec14
Create Date: 2020-07-02 20:31:05.041153
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b3baf70b4a4b"  # pragma: allowlist secret
down_revision = "b6660d01ec14"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("fk", "tasks", type_="foreignkey")
    op.create_foreign_key(
        "fk",
        "tasks",
        "assets",
        ["asset_id"],
        ["asset_id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("fk", "tasks", type_="foreignkey")
    op.create_foreign_key("fk", "tasks", "assets", ["asset_id"], ["asset_id"])
    # ### end Alembic commands ###