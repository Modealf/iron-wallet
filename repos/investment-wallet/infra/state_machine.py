import uuid
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


class IllegalStateTransition(Exception):
    pass


async def guarded_transition(session: AsyncSession, model, row_id: uuid.UUID, *, expected: str, new: str) -> None:
    result = await session.execute(
        update(model).where(model.id == row_id, model.status == expected).values(status=new).returning(model.id)
    )
    if result.scalar_one_or_none() is None:
        raise IllegalStateTransition(f"{model.__name__}({row_id}) not in state {expected!r}")
