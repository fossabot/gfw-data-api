"""empty message

Revision ID: bb1ed7d0e219
Revises: e47ec2fc3c51
Create Date: 2020-04-27 21:28:06.078081

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "bb1ed7d0e219"
down_revision = "e47ec2fc3c51"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("assets", sa.Column("asset_id", postgresql.UUID(), nullable=False))
    op.add_column(
        "assets",
        sa.Column(
            "creation_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "history",
            postgresql.ARRAY(postgresql.JSONB(astext_type=sa.Text())),
            nullable=True,
        ),
    )
    op.add_column("assets", sa.Column("is_managed", sa.Boolean(), nullable=True))
    op.add_column("assets", sa.Column("status", sa.String(), nullable=False))
    op.alter_column("assets", "asset_uri", existing_type=sa.VARCHAR(), nullable=False)
    op.drop_index("idx_geostore_gfw_bbox", table_name="geostore")
    op.add_column("versions", sa.Column("is_mutable", sa.Boolean(), nullable=True))
    op.add_column(
        "versions",
        sa.Column("source_uri", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.drop_column("versions", "has_90_27008_tiles")
    op.drop_column("versions", "has_90_9876_tiles")
    op.drop_column("versions", "has_10_40000_tiles")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "versions",
        sa.Column(
            "has_10_40000_tiles", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "versions",
        sa.Column(
            "has_90_9876_tiles", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "versions",
        sa.Column(
            "has_90_27008_tiles", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
    )
    op.drop_column("versions", "source_uri")
    op.drop_column("versions", "is_mutable")
    op.create_index("idx_geostore_gfw_bbox", "geostore", ["gfw_bbox"], unique=False)
    op.alter_column("assets", "asset_uri", existing_type=sa.VARCHAR(), nullable=True)
    op.drop_column("assets", "status")
    op.drop_column("assets", "is_managed")
    op.drop_column("assets", "history")
    op.drop_column("assets", "creation_options")
    op.drop_column("assets", "asset_id")
    # ### end Alembic commands ###
