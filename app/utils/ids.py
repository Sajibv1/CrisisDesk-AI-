from uuid import uuid4


def new_report_id() -> str:
    return f"report_{uuid4().hex[:12]}"
