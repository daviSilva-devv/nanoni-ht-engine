from fastapi import Depends
from sqlalchemy.orm import Session

from nanoni.core.db import get_db

DB = Depends(get_db)


def db_session(db: Session = DB) -> Session:
    return db
