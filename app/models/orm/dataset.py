from .base import Base, db


class Dataset(Base):
    __tablename__ = 'datasets'
    dataset = db.Column(db.String, primary_key=True)
    metadata = db.Column(db.JSONB)

