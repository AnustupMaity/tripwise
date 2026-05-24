# TripWise V1 Contract

## Product Decisions Locked

- Full feature flow in V1.
- Login supports email or phone with OTP or password.
- Guest mode is strict read-only.
- Member-added expenses require admin approval.
- Email notifications in V1.
- Web first, then mobile parity.

## Domain Invariants

1. A trip has exactly one leader (admin) at creation.
2. Pending or rejected invites are excluded from split computation.
3. Closed trips are immutable except report download operations.
4. Expense totals must equal sum of payer contributions and sum of split allocations.
5. Guest members can never create, edit, approve, dispute, or mark payments.

## Realtime Events

- trip_created
- trip_member_invited
- trip_member_status_changed
- expense_added
- expense_approved
- expense_rejected
- dispute_raised
- dispute_resolved
- payment_marked_paid
- trip_closed
