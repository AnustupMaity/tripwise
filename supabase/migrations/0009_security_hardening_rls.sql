-- Security hardening for exposed Supabase objects.
--
-- The backend connects with the Postgres service role, so these deny-all
-- policies do not block the app. They only remove anonymous/authenticated
-- access through the public API surface.

create or replace function public.rls_auto_enable()
returns void
language plpgsql
security invoker
as $$
begin
    -- Intentionally a no-op: the repo no longer exposes an executable
    -- SECURITY DEFINER helper through the public schema.
    return;
end;
$$;

revoke execute on function public.rls_auto_enable() from anon, authenticated;

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
        execute format(
            'create policy deny_public_access on public.%I for all to anon, authenticated using (false) with check (false)',
            table_name
        );
    end loop;
end;
$$;