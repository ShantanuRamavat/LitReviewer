"""
FastAPI dependency for injecting an async database session.

Route handlers declare ``session: AsyncSession = Depends(get_db)`` to receive
a session that is:
- Automatically committed when the handler returns successfully.
- Automatically rolled back if the handler raises an exception.
- Closed in the ``finally`` block regardless of outcome.

Example::

    from app.db.postgres.session import get_db

    @router.get("/example")
    async def example(session: AsyncSession = Depends(get_db)):
        result = await session.execute(select(MyModel))
        return result.scalars().all()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.engine import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` as a FastAPI dependency.

    The session lifecycle follows the standard unit-of-work pattern:

    1. A new session is opened from the factory.
    2. The session is yielded to the route handler.
    3. On clean exit the session is **committed**.
    4. If an exception propagates, the session is **rolled back** before
       re-raising so the database is never left in a partial state.
    5. The session is always **closed** in the ``finally`` block.

    Yields:
        An ``AsyncSession`` bound to the current request.

    Raises:
        Any exception raised by the route handler (after rolling back).
    """
    factory = get_session_factory()

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
