import json
from typing import Any

from sqlalchemy.orm import Session

from shift_scheduler.models import EditLog


def write_log(
    db: Session,
    kind: str,
    payload: dict[str, Any],
    *,
    actor_ip: str | None = None,
) -> EditLog:
    """Append an EditLog row recording an edit action.

    The row is added to the session and flushed so callers can rely on
    `row.id`, but the transaction is left open for the caller to commit
    alongside the mutation it audits.
    """
    row = EditLog(
        ip=actor_ip,
        action=kind,
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
    db.add(row)
    db.flush()
    return row
