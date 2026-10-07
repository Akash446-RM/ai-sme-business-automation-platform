"""Generic repository providing reusable persistence primitives."""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.pagination import PageParams

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Thin data access helper shared by the concrete repositories.

    Repositories only know how to read and write rows; all business rules live
    in the service layer.
    """

    def __init__(self, db: Session, model: Type[ModelType]) -> None:
        self.db = db
        self.model = model

    def get(self, entity_id: int) -> Optional[ModelType]:
        return self.db.get(self.model, entity_id)

    def get_many(self, entity_ids: Sequence[int]) -> List[ModelType]:
        if not entity_ids:
            return []
        return list(
            self.db.execute(
                select(self.model).where(self.model.id.in_(entity_ids))  # type: ignore[attr-defined]
            ).scalars()
        )

    def list_all(self) -> List[ModelType]:
        return list(self.db.execute(select(self.model)).scalars())

    def count(self, statement: Optional[Select] = None) -> int:
        if statement is None:
            statement = select(func.count()).select_from(self.model)
            return int(self.db.execute(statement).scalar_one())
        subquery = statement.order_by(None).subquery()
        return int(
            self.db.execute(select(func.count()).select_from(subquery)).scalar_one()
        )

    def paginate(self, statement: Select, params: PageParams) -> tuple[List[Any], int]:
        """Return one page of rows plus the total matching row count."""
        total = self.count(statement)
        rows = list(
            self.db.execute(statement.offset(params.offset).limit(params.limit)).scalars()
        )
        return rows, total

    def create(self, **values: Any) -> ModelType:
        instance = self.model(**values)
        self.db.add(instance)
        self.db.flush()
        return instance

    def update(self, instance: ModelType, values: Dict[str, Any]) -> ModelType:
        for field, value in values.items():
            setattr(instance, field, value)
        self.db.flush()
        return instance

    def delete(self, instance: ModelType) -> None:
        self.db.delete(instance)
        self.db.flush()

    def exists(self, **filters: Any) -> bool:
        statement = select(func.count()).select_from(self.model)
        for field, value in filters.items():
            statement = statement.where(getattr(self.model, field) == value)
        return int(self.db.execute(statement).scalar_one()) > 0
