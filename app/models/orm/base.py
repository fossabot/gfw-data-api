from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy_utils import EmailType, generic_repr
from geoalchemy2 import Geometry

from ...application import db

db.JSONB, db.UUID, db.ARRAY, db.EmailType, db.Geometry = (JSONB, UUID, ARRAY, EmailType, Geometry)


@generic_repr
class Base(db.Model):
    __abstract__ = True
    created_on = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.now())
    updated_on = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=db.func.now())

