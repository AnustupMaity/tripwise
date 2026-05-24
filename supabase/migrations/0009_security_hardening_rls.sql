-- Security hardening for exposed Supabase objects.
--
-- The backend connects with the Postgres service role, so these deny-all
-- policies do not block the app. They only remove anonymous/authenticated
-- access through the public API surface.

do $$
begin
    if exists (
        select 1
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname = 'rls_auto_enable'
          and pg_get_function_identity_arguments(p.oid) = ''
    ) then
        execute 'revoke execute on function public.rls_auto_enable() from public, anon, authenticated';
    end if;
end;
$$;

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