# backend/app/models/__init__.py
# Import every model so Base.metadata is fully populated before create_all()

from app.models.user    import User, Trainee, Coach       # noqa: F401
from app.models.move    import MoveReference              # noqa: F401
from app.models.session import Session, Detection, Recording  # noqa: F401
from app.models.rag     import RagDocument, RagQuery, Feedback  # noqa: F401