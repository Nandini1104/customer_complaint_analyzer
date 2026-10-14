"""SQLAlchemy models. The shared `db` object lives here to avoid circular imports."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .customer import Customer          # noqa: E402
from .complaint import Complaint        # noqa: E402
from .sentiment import SentimentResult  # noqa: E402
from .category import Category          # noqa: E402
from .history import ComplaintHistory   # noqa: E402
from .user import User, Setting         # noqa: E402

__all__ = ["db", "Customer", "Complaint", "SentimentResult", "Category",
           "ComplaintHistory", "User", "Setting"]
