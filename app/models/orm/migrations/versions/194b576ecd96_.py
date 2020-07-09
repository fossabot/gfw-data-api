"""empty message.

Revision ID: 194b576ecd96
Revises: a3519919b1b6
Create Date: 2020-07-08 14:27:53.296531
"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "194b576ecd96"  # pragma: allowlist secret
down_revision = "a3519919b1b6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "assets",
        "change_log",
        existing_type=postgresql.ARRAY(postgresql.JSONB(astext_type=sa.Text())),
        nullable=False,
        existing_server_default=sa.text("ARRAY[]::jsonb[]"),
    )
    op.alter_column(
        "assets",
        "creation_options",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "assets",
        "fields",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        existing_server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "assets",
        "metadata",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "assets",
        "stats",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.drop_column("versions", "source_uri")
    op.drop_column("versions", "source_type")
    op.drop_column("versions", "creation_options")
    op.drop_column("versions", "has_geostore")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "versions",
        sa.Column(
            "has_geostore",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "versions",
        sa.Column(
            "creation_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "versions", sa.Column("source_type", sa.VARCHAR(), autoincrement=False)
    )  # , nullable=False
    op.add_column(
        "versions",
        sa.Column("source_uri", postgresql.ARRAY(sa.VARCHAR()), autoincrement=False),
    )  # , nullable=True
    op.alter_column(
        "assets",
        "stats",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "assets",
        "metadata",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "assets",
        "fields",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        existing_server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "assets",
        "creation_options",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "assets",
        "change_log",
        existing_type=postgresql.ARRAY(postgresql.JSONB(astext_type=sa.Text())),
        nullable=True,
        existing_server_default=sa.text("ARRAY[]::jsonb[]"),
    )
    # ### end Alembic commands ###
