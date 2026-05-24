-- Expense approval and lookup performance indexes

create index if not exists idx_expenses_trip_status_created
    on public.expenses(trip_id, status, created_at desc);

create index if not exists idx_expense_payers_expense_id
    on public.expense_payers(expense_id);

create index if not exists idx_expense_splits_expense_id
    on public.expense_splits(expense_id);
