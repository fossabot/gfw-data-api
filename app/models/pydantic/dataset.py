from pydantic import BaseModel
from typing import List, Optional

from .base import Base
from .metadata import DatasetMetadata


class Dataset(Base):
    dataset: str
    metadata: DatasetMetadata
    versions: Optional[List[str]] = list()


class DatasetCreateIn(BaseModel):
    metadata: DatasetMetadata


class DatasetUpdateIn(BaseModel):
    metadata: DatasetMetadata
