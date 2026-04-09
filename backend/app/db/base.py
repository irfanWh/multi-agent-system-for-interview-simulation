import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Get Database URL from environment (defaulting to a local instance if not provided)
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql+asyncpg://interviewai_user:change_me_postgres_password@localhost:5432/interviewai_db"
)

# Ensure the driver is set to postgresql+asyncpg for async usage
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

# Escape passwords containing @ (e.g. irfan123@)
if "@@" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("@@", "%40@")

# SQLAlchemy Async Engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Declarative Base for ORM Models
Base = declarative_base()

# Dependency for FastAPI to get a database session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
