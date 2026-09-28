from flask_login import current_user

from models import db
from models.core import AuditLog


def log_action(action, record_type, record_id=None, old_value="", new_value=""):
    user_id = current_user.id if getattr(current_user, "is_authenticated", False) else None
    db.session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            record_type=record_type,
            record_id=record_id,
            old_value=old_value,
            new_value=new_value,
        )
    )
