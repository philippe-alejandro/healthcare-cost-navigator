from alembic import op
import sqlalchemy as sa


revision = "20240914_000001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table(
        "providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.String(length=16), nullable=False, unique=True),
        sa.Column("provider_name", sa.String(length=255), nullable=False),
        sa.Column("provider_city", sa.String(length=128), nullable=False),
        sa.Column("provider_state", sa.String(length=2), nullable=False),
        sa.Column("provider_zip_code", sa.String(length=10), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_providers_zip", "providers", ["provider_zip_code"]) 

    op.create_table(
        "drgs",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_drgs_description", "drgs", ["description"])

    op.create_table(
        "zip_codes",
        sa.Column("zip", sa.String(length=10), primary_key=True),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
    )
    op.create_index("ix_zip_codes_zip", "zip_codes", ["zip"]) 

    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("drg_code", sa.Integer(), sa.ForeignKey("drgs.code"), nullable=False),
        sa.Column("total_discharges", sa.Integer()),
        sa.Column("average_covered_charges", sa.Numeric(12, 2)),
        sa.Column("average_total_payments", sa.Numeric(12, 2)),
        sa.Column("average_medicare_payments", sa.Numeric(12, 2)),
    )
    op.create_index("ix_prices_provider", "prices", ["provider_id"]) 
    op.create_index("ix_prices_drg", "prices", ["drg_code"]) 
    op.create_index("ix_prices_drg_cost", "prices", ["drg_code", "average_covered_charges"]) 

    op.create_table(
        "star_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 10", name="ck_star_ratings_range"),
    )
    op.create_index("ix_star_ratings_provider", "star_ratings", ["provider_id"]) 


def downgrade() -> None:
    op.drop_index("ix_star_ratings_provider", table_name="star_ratings")
    op.drop_table("star_ratings")

    op.drop_index("ix_prices_drg_cost", table_name="prices")
    op.drop_index("ix_prices_drg", table_name="prices")
    op.drop_index("ix_prices_provider", table_name="prices")
    op.drop_table("prices")

    op.drop_index("ix_zip_codes_zip", table_name="zip_codes")
    op.drop_table("zip_codes")

    op.drop_index("ix_drgs_description", table_name="drgs")
    op.drop_table("drgs")

    op.drop_index("ix_providers_zip", table_name="providers")
    op.drop_table("providers")


