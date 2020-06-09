"""empty message

Revision ID: 3a7dda631399
Revises: b275927c8c2d
Create Date: 2020-05-18 03:44:51.032742

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3a7dda631399"  # pragma: allowlist secret
down_revision = "b275927c8c2d"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("assets", "is_managed", existing_type=sa.BOOLEAN(), nullable=False)
    op.create_unique_constraint(
        "uq_asset_type", "assets", ["dataset", "version", "asset_type"]
    )
    op.create_unique_constraint("uq_asset_uri", "assets", ["asset_uri"])
    op.add_column("versions", sa.Column("status", sa.String(), nullable=False))
    op.drop_column("versions", "fields")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "versions",
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_column("versions", "status")
    op.drop_constraint("uq_asset_uri", "assets", type_="unique")
    op.drop_constraint("uq_asset_type", "assets", type_="unique")
    op.alter_column("assets", "is_managed", existing_type=sa.BOOLEAN(), nullable=True)
    # ### end Alembic commands ###