from __future__ import annotations


def trip_created_template(*, trip_name: str, creator_name: str) -> tuple[str, str]:
    title = "New trip created"
    message = f"{creator_name} created '{trip_name}'. Open TripWise to review members and start tracking expenses."
    return title, message


def trip_invite_sent_template(*, trip_name: str, inviter_name: str) -> tuple[str, str]:
    title = "You are invited"
    message = f"{inviter_name} invited you to '{trip_name}'. Accept the invite in TripWise to join expense tracking."
    return title, message


def trip_invite_response_template(*, trip_name: str, member_name: str, accepted: bool) -> tuple[str, str]:
    title = "Invite accepted" if accepted else "Invite rejected"
    action = "accepted" if accepted else "rejected"
    message = f"{member_name} {action} the invite for '{trip_name}'."
    return title, message


def expense_added_template(*, amount: float, description: str, added_by_name: str) -> tuple[str, str]:
    title = "New expense added"
    message = f"{added_by_name} added Rs {amount:.2f} for '{description}'."
    return title, message


def expense_approved_template(*, amount: float, description: str, approved_by_name: str) -> tuple[str, str]:
    title = "Expense approved"
    message = f"Leader {approved_by_name} approved Rs {amount:.2f} for '{description}'."
    return title, message


def expense_rejected_template(*, amount: float, description: str, rejected_by_name: str) -> tuple[str, str]:
    title = "Expense rejected"
    message = f"Leader {rejected_by_name} rejected Rs {amount:.2f} for '{description}'."
    return title, message


def dispute_raised_template(*, expense_label: str, raised_by_name: str) -> tuple[str, str]:
    title = "Dispute raised"
    message = f"{raised_by_name} raised a dispute on expense '{expense_label}'."
    return title, message


def dispute_resolved_template(*, expense_label: str, resolved_by_name: str) -> tuple[str, str]:
    title = "Dispute resolved"
    message = f"{resolved_by_name} resolved the dispute for expense '{expense_label}'."
    return title, message