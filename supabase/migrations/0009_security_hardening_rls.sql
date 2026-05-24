-- Security hardening for exposed Supabase objects.
--
-- The backend connects with the Postgres service role, so these deny-all
-- policies do not block the app. They only remove anonymous/authenticated
-- access through the public API surface.

drop function if exists public.rls_auto_enable();

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'audit_logs',
        'auth_otp_challenges',
        'auth_password_reset_tokens',
        'auth_pending_registrations',
        'auth_rate_limits',
        'auth_sessions',
        'dispute_comments',
        'disputes',
        'expense_payers',
        'expense_splits',
        'expenses',
        'notifications',
        'payments',
        'profiles',
        'reports',
        'trip_members',
        'trips'
    ] loop
        execute format('drop policy if exists deny_public_access on public.%I', table_name);
        execute format(
            'create policy deny_public_access on public.%I for all to anon, authenticated using (false) with check (false)',
            table_name
        );
    end loop;
end;
$$;