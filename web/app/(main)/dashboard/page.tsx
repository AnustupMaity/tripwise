"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { resolveApiBase } from "../../lib/api-base";

type Trip = {
  trip_id: string;
  name: string;
  status: string;
  member_count: number;
  my_role?: string;
};

type Member = {
  memberId: string;
  role: string;
  inviteStatus: string;
  canEdit: boolean;
  identifier: string | null;
};

type PendingExpense = {
  expense_id: string;
  description: string;
  amount: number;
  status: string;
};

type ExpenseItem = {
  expense_id: string;
  description: string;
  amount: number;
  status: string;
  split_type: string;
  created_at: string;
};

type DisputeItem = {
  dispute_id: string;
  expense_id: string;
  status: string;
  comment: string;
  disputed_amount: number | null;
  created_at: string;
};

type SettlementRow = {
  fromMemberId: string;
  toMemberId: string;
  amount: number;
};

type ReportItem = {
  report_id: string;
  report_type: string;
  format: string;
  file_url: string;
  created_at: string;
  emailed_to: string[];
};

type InAppNotification = {
  notification_id: string;
  event_type: string;
  payload: {
    title?: string;
    message?: string;
    tripId?: string;
  };
  created_at: string;
};

type PayerDraft = {
  memberId: string;
  amountPaid: string;
};

type SplitDraft = {
  memberId: string;
  include: boolean;
  amountOwed: string;
  percentage: string;
};

type SplitPreset = "equal" | "dutch" | "percentage" | "selective" | "custom";

type SessionProfile = {
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  upiId?: string | null;
  upiNumber?: string | null;
};

type CreateMode = "self" | "dynamic";

type MemberDraft = {
  name: string;
  email: string;
  registered: boolean | null;
};

type LedgerRow = {
  expenseId: string;
  createdAt: string;
  description: string;
  status: string;
  splitType: string;
  amount: number;
  runningTotal: number;
};

type ExpenseTemplate = { label: string; description: string };

const EXPENSE_TEMPLATES: ExpenseTemplate[] = [
  { label: "Cab", description: "Cab ride" },
  { label: "Food", description: "Group meal" },
  { label: "Tickets", description: "Entry tickets" },
];

const CURRENCIES = ["INR", "USD", "EUR", "GBP"];

function uiRoleLabel(role?: string): string {
  return role === "creator" || role === "admin" ? "Leader" : "Member";
}

function toMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

function parseMoney(value: string): number {
  const parsed = Number(value);
  if (Number.isNaN(parsed) || parsed < 0) {
    return 0;
  }
  return toMoney(parsed);
}

const API_BASE = resolveApiBase();

function getSessionToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("tripwise_session_token") ?? "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const sessionToken = getSessionToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionToken ? { "x-session-token": sessionToken } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function memberLabel(member: Member): string {
  const uiRole = member.role === "admin" ? "Leader" : "Member";
  return member.identifier ? member.identifier : `${member.memberId.slice(0, 8)} (${uiRole})`;
}

export default function DashboardPage() {
  const [actorIdentifier, setActorIdentifier] = useState("");
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>({});
  const [tripName, setTripName] = useState("");
  const [createMode, setCreateMode] = useState<CreateMode>("dynamic");
  const [newTripMemberCount, setNewTripMemberCount] = useState(1);
  const [memberDrafts, setMemberDrafts] = useState<MemberDraft[]>([{ name: "", email: "", registered: null }]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [selectedTripId, setSelectedTripId] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);
  const [pendingExpenses, setPendingExpenses] = useState<PendingExpense[]>([]);
  const [disputes, setDisputes] = useState<DisputeItem[]>([]);
  const [settlementRows, setSettlementRows] = useState<SettlementRow[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [notifications, setNotifications] = useState<InAppNotification[]>([]);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [profileNickname, setProfileNickname] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileUpiId, setProfileUpiId] = useState("");
  const [profileUpiNumber, setProfileUpiNumber] = useState("");
  const [profileEmailOtp, setProfileEmailOtp] = useState("");
  const [profileEmailOtpRequested, setProfileEmailOtpRequested] = useState(false);

  const [expenseModalOpen, setExpenseModalOpen] = useState(false);
  const [expenseDescription, setExpenseDescription] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("0");
  const [splitPreset, setSplitPreset] = useState<SplitPreset>("equal");
  const [payerDrafts, setPayerDrafts] = useState<PayerDraft[]>([]);
  const [splitDrafts, setSplitDrafts] = useState<SplitDraft[]>([]);

  const [disputeExpenseId, setDisputeExpenseId] = useState("");
  const [disputeComment, setDisputeComment] = useState("");
  const [disputeAmount, setDisputeAmount] = useState("");
  const [resolveCommentById, setResolveCommentById] = useState<Record<string, string>>({});
  const [reportFormat, setReportFormat] = useState("pdf");
  const [reportType, setReportType] = useState("settlement");
  const [reportEmailsCsv, setReportEmailsCsv] = useState("");
  const [payMethod, setPayMethod] = useState("manual");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [quickAddReason, setQuickAddReason] = useState("");
  const [quickAddAmount, setQuickAddAmount] = useState("");
  const [quickAddPayerId, setQuickAddPayerId] = useState("");
  const [tripCurrencies, setTripCurrencies] = useState<Record<string, string>>({});
  const [publicSummaryLink, setPublicSummaryLink] = useState("");

  const selectedTrip = useMemo(() => trips.find((t) => t.trip_id === selectedTripId) ?? null, [trips, selectedTripId]);
  const hasTripSelection = Boolean(selectedTripId && selectedTrip);
  const currentCurrency = selectedTripId ? (tripCurrencies[selectedTripId] ?? "INR") : "INR";

  function openProfileEditor() {
    setProfileName(sessionProfile.name ?? "");
    setProfileNickname(sessionProfile.nickname ?? "");
    setProfileEmail(sessionProfile.email ?? "");
    setProfilePhone(sessionProfile.phone ?? "");
    setProfileUpiId(sessionProfile.upiId ?? "");
    setProfileUpiNumber(sessionProfile.upiNumber ?? "");
    setProfileEmailOtp("");
    setProfileEmailOtpRequested(false);
    setProfileModalOpen(true);
    setError("");
  }

  function closeProfileEditor() {
    setProfileModalOpen(false);
    setProfileEmailOtp("");
    setProfileEmailOtpRequested(false);
  }

  async function requestEmailChangeOtp() {
    try {
      setProfileSaving(true);
      setError("");
      const email = profileEmail.trim();
      if (!email) {
        throw new Error("Enter a new email first.");
      }
      await fetchJson<{ message?: string; otp?: string }>("/auth/profile/email/request-otp", {
        method: "POST",
        body: JSON.stringify({
          session_token: getSessionToken(),
          email,
        }),
      });
      setProfileEmailOtpRequested(true);
      setNotice("Verification code sent to the new email address.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to send email verification code.");
    } finally {
      setProfileSaving(false);
    }
  }

  async function saveProfileDetails() {
    try {
      setProfileSaving(true);
      setError("");
      const data = await fetchJson<SessionProfile & { userId?: string; requiresProfileCompletion?: boolean }>("/auth/profile/complete", {
        method: "POST",
        body: JSON.stringify({
          session_token: getSessionToken(),
          name: profileName.trim() || null,
          phone: profilePhone.trim(),
          nickname: profileNickname.trim() || null,
          email: profileEmail.trim() || null,
          email_otp: profileEmailOtp.trim() || null,
          upi_id: profileUpiId.trim() || null,
          upi_number: profileUpiNumber.trim() || null,
        }),
      });
      setSessionProfile((current) => ({
        ...current,
        name: data.name ?? profileName.trim(),
        nickname: data.nickname ?? profileNickname.trim(),
        email: data.email ?? profileEmail.trim(),
        phone: data.phone ?? profilePhone.trim(),
        upiId: data.upiId ?? (profileUpiId.trim() || undefined),
        upiNumber: data.upiNumber ?? (profileUpiNumber.trim() || undefined),
      }));
      setActorIdentifier(data.email ?? profileEmail.trim());
      setNotice("Profile updated successfully.");
      closeProfileEditor();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update profile.");
    } finally {
      setProfileSaving(false);
    }
  }

  useEffect(() => {
    async function hydrateActorIdentifier() {
      try {
        const token = getSessionToken();
        if (!token) {
          return;
        }
        const data = await fetchJson<SessionProfile>("/auth/session/validate", {
          method: "POST",
          body: JSON.stringify({ session_token: token }),
        });
        setSessionProfile(data);
        if (data.email) {
          setActorIdentifier(data.email);
        }
      } catch {
        // AppShell handles redirect for invalid sessions.
      }
    }
    void hydrateActorIdentifier();
  }, []);

  useEffect(() => {
    if (!actorIdentifier) {
      return;
    }
    void loadTrips();
  }, [actorIdentifier]);

  useEffect(() => {
    const raw = localStorage.getItem("tripwise_trip_currencies");
    if (!raw) {
      return;
    }
    try {
      setTripCurrencies(JSON.parse(raw));
    } catch {
      setTripCurrencies({});
    }
  }, []);

  useEffect(() => {
    if (payerDrafts.length === 0) {
      return;
    }
    const total = parseMoney(expenseAmount);
    setPayerDrafts((current) => {
      if (current.length === 0) {
        return current;
      }
      const lastIndex = current.length - 1;
      const othersTotal = current.slice(0, lastIndex).reduce((acc, payer) => acc + parseMoney(payer.amountPaid), 0);
      const remainder = toMoney(Math.max(0, total - othersTotal));
      const currentLastValue = parseMoney(current[lastIndex].amountPaid);
      if (Math.abs(currentLastValue - remainder) < 0.01) {
        return current;
      }
      const next = [...current];
      next[lastIndex] = {
        ...next[lastIndex],
        amountPaid: remainder.toFixed(2),
      };
      return next;
    });
  }, [expenseAmount, payerDrafts]);

  useEffect(() => {
    if (!(splitPreset === "dutch" || splitPreset === "custom" || splitPreset === "selective")) {
      return;
    }
    const total = parseMoney(expenseAmount);
    setSplitDrafts((current) => {
      const includedIndexes = current
        .map((split, index) => ({ split, index }))
        .filter((item) => item.split.include)
        .map((item) => item.index);
      if (includedIndexes.length === 0) {
        return current;
      }
      const lastIndex = includedIndexes[includedIndexes.length - 1];
      const othersTotal = includedIndexes
        .filter((index) => index !== lastIndex)
        .reduce((acc, index) => acc + parseMoney(current[index].amountOwed), 0);
      const remainder = toMoney(Math.max(0, total - othersTotal));
      const currentLastValue = parseMoney(current[lastIndex].amountOwed);
      if (Math.abs(currentLastValue - remainder) < 0.01) {
        return current;
      }
      const next = [...current];
      next[lastIndex] = {
        ...next[lastIndex],
        amountOwed: remainder.toFixed(2),
      };
      return next;
    });
  }, [expenseAmount, splitPreset, splitDrafts]);

  const acceptedEditableMembers = useMemo(
    () => members.filter((member) => member.inviteStatus === "accepted" && member.canEdit),
    [members],
  );

  const acceptedMemberCount = useMemo(
    () => members.filter((member) => member.inviteStatus === "accepted").length,
    [members],
  );

  const liveLedgerRows = useMemo<LedgerRow[]>(() => {
    const chronological = [...expenses].sort(
      (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
    );
    let runningTotal = 0;
    const rows = chronological.map((expense) => {
      runningTotal = toMoney(runningTotal + expense.amount);
      return {
        expenseId: expense.expense_id,
        createdAt: expense.created_at,
        description: expense.description,
        status: expense.status,
        splitType: expense.split_type,
        amount: expense.amount,
        runningTotal,
      };
    });
    return rows.reverse();
  }, [expenses]);

  const autoBalancedSplitIndex = useMemo(() => {
    if (!(splitPreset === "dutch" || splitPreset === "custom" || splitPreset === "selective")) {
      return -1;
    }
    const includedIndexes = splitDrafts
      .map((split, index) => ({ split, index }))
      .filter((item) => item.split.include)
      .map((item) => item.index);
    if (includedIndexes.length === 0) {
      return -1;
    }
    return includedIndexes[includedIndexes.length - 1];
  }, [splitDrafts, splitPreset]);

  const payerTotal = useMemo(
    () => payerDrafts.reduce((acc, payer) => acc + parseMoney(payer.amountPaid), 0),
    [payerDrafts],
  );

  const splitAmountTotal = useMemo(
    () => splitDrafts.reduce((acc, split) => (split.include ? acc + parseMoney(split.amountOwed) : acc), 0),
    [splitDrafts],
  );

  function formatMoney(value: number): string {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: currentCurrency, maximumFractionDigits: 2 }).format(value);
  }

  async function loadTrips() {
    if (!actorIdentifier.trim()) {
      setError("Active session user not found.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      const result = await fetchJson<{ trips: Trip[] }>("/trips");
      setTrips(result.trips ?? []);
      if (result.trips?.length) {
        const firstId = selectedTripId && result.trips.some((t) => t.trip_id === selectedTripId)
          ? selectedTripId
          : result.trips[0].trip_id;
        setSelectedTripId(firstId);
        await loadTripDetails(firstId);
      }
      setNotice(`Loaded ${result.trips?.length ?? 0} trip(s).`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load trips.");
    } finally {
      setLoading(false);
    }
  }

  async function loadTripDetails(tripId: string) {
    if (!tripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");

      const [memberData, expenseData, pendingData, disputeData, settlementData, reportData, notificationData] = await Promise.all([
        fetchJson<{ members: Member[] }>(`/trips/${tripId}/members`),
        fetchJson<{ expenses: ExpenseItem[] }>(`/expenses?trip_id=${encodeURIComponent(tripId)}`),
        fetchJson<{ pendingExpenses: PendingExpense[] }>(
          `/expenses/pending?trip_id=${encodeURIComponent(tripId)}&admin_identifier=${encodeURIComponent(actorIdentifier)}`,
        ),
        fetchJson<{ disputes: DisputeItem[] }>(`/disputes?trip_id=${encodeURIComponent(tripId)}`),
        fetchJson<{ whoOwesWhom: SettlementRow[] }>(`/payments/settlement?trip_id=${encodeURIComponent(tripId)}`),
        fetchJson<{ reports: ReportItem[] }>(`/reports?trip_id=${encodeURIComponent(tripId)}`),
        fetchJson<{ notifications: InAppNotification[] }>(
          `/notifications/in-app?identifier=${encodeURIComponent(actorIdentifier.trim())}&limit=40`,
        ),
      ]);

      setMembers(memberData.members ?? []);
      setExpenses(expenseData.expenses ?? []);
      setPendingExpenses(pendingData.pendingExpenses ?? []);
      setDisputes(disputeData.disputes ?? []);
      setSettlementRows(settlementData.whoOwesWhom ?? []);
      setReports(reportData.reports ?? []);
      setNotifications(notificationData.notifications ?? []);
      setDisputeExpenseId((current) => {
        if (current && (expenseData.expenses ?? []).some((e) => e.expense_id === current)) {
          return current;
        }
        return expenseData.expenses?.[0]?.expense_id ?? "";
      });
      setNotice("Trip data refreshed.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load trip details.");
    } finally {
      setLoading(false);
    }
  }

  function openExpenseComposer() {
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    if (acceptedEditableMembers.length === 0) {
      setError("No accepted editable members available.");
      return;
    }

    const defaultMember = acceptedEditableMembers[0].memberId;
    setSplitPreset("equal");
    setExpenseDescription("");
    setExpenseAmount("0");
    setPayerDrafts([{ memberId: defaultMember, amountPaid: "0" }]);
    setSplitDrafts(
      acceptedEditableMembers.map((m) => ({
        memberId: m.memberId,
        include: true,
        amountOwed: "",
        percentage: "",
      })),
    );
    setExpenseModalOpen(true);
  }

  function addPayerRow() {
    const fallbackMember = acceptedEditableMembers.find((m) => !payerDrafts.some((p) => p.memberId === m.memberId));
    if (!fallbackMember) {
      return;
    }
    setPayerDrafts((current) => [...current, { memberId: fallbackMember.memberId, amountPaid: "0" }]);
  }

  function removePayerRow(index: number) {
    setPayerDrafts((current) => current.filter((_, idx) => idx !== index));
  }

  async function submitAdvancedExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    if (!expenseDescription.trim()) {
      setError("Expense description is required.");
      return;
    }

    const amount = Number(expenseAmount);
    if (Number.isNaN(amount) || amount <= 0) {
      setError("Expense amount must be greater than 0.");
      return;
    }

    const paidBy = payerDrafts
      .map((payer) => ({ member_id: payer.memberId, amount_paid: Number(payer.amountPaid) }))
      .filter((payer) => payer.member_id && payer.amount_paid > 0);

    const payerTotal = paidBy.reduce((acc, row) => acc + row.amount_paid, 0);
    if (paidBy.length === 0 || Math.abs(payerTotal - amount) > 0.01) {
      setError("Payer rows must sum exactly to total amount.");
      return;
    }

    let splitTypeForApi: "equal" | "unequal" | "percentage" | "selective" | "custom" = "equal";
    const splitsForApi: Array<{ member_id: string; amount_owed?: number; percentage?: number; excluded: boolean }> = [];

    if (splitPreset === "equal") {
      const allIncluded = splitDrafts.every((row) => row.include);
      const anyManual = splitDrafts.some((row) => row.amountOwed.trim().length > 0);
      if (!allIncluded || anyManual) {
        splitTypeForApi = "selective";
        splitDrafts.forEach((row) => {
          const amountOwed = row.amountOwed.trim() ? Number(row.amountOwed) : undefined;
          splitsForApi.push({
            member_id: row.memberId,
            amount_owed: amountOwed,
            excluded: !row.include,
          });
        });
      }
    } else if (splitPreset === "dutch") {
      splitTypeForApi = "unequal";
      splitDrafts.forEach((row) => {
        if (!row.include) {
          return;
        }
        splitsForApi.push({ member_id: row.memberId, amount_owed: Number(row.amountOwed), excluded: false });
      });
    } else if (splitPreset === "percentage") {
      splitTypeForApi = "percentage";
      splitDrafts.forEach((row) => {
        if (!row.include) {
          return;
        }
        splitsForApi.push({ member_id: row.memberId, percentage: Number(row.percentage), excluded: false });
      });
    } else if (splitPreset === "selective") {
      splitTypeForApi = "selective";
      splitDrafts.forEach((row) => {
        const amountOwed = row.amountOwed.trim() ? Number(row.amountOwed) : undefined;
        splitsForApi.push({ member_id: row.memberId, amount_owed: amountOwed, excluded: !row.include });
      });
    } else {
      splitTypeForApi = "custom";
      splitDrafts.forEach((row) => {
        if (!row.include) {
          return;
        }
        splitsForApi.push({ member_id: row.memberId, amount_owed: Number(row.amountOwed), excluded: false });
      });
    }

    try {
      setLoading(true);
      setError("");
      await fetchJson("/expenses/", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          actor_identifier: actorIdentifier.trim(),
          amount,
          description: expenseDescription.trim(),
          split_type: splitTypeForApi,
          paid_by: paidBy,
          splits: splitsForApi,
        }),
      });
      setExpenseModalOpen(false);
      await loadTripDetails(selectedTripId);
      setNotice("Expense added.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to add expense.");
    } finally {
      setLoading(false);
    }
  }

  async function onQuickAddExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId || !quickAddPayerId) {
      setError("Select a trip and payer for quick add.");
      return;
    }
    const amount = Number(quickAddAmount);
    if (!quickAddReason.trim() || Number.isNaN(amount) || amount <= 0) {
      setError("Quick add requires valid reason and amount.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson("/expenses/", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          actor_identifier: actorIdentifier.trim(),
          amount,
          description: quickAddReason.trim(),
          split_type: "equal",
          paid_by: [{ member_id: quickAddPayerId, amount_paid: amount }],
          splits: [],
        }),
      });
      setQuickAddReason("");
      setQuickAddAmount("");
      await loadTripDetails(selectedTripId);
      setNotice("Quick expense added.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Quick add failed.");
    } finally {
      setLoading(false);
    }
  }

  function onChangeTripCurrency(value: string) {
    if (!selectedTripId) {
      return;
    }
    const next = { ...tripCurrencies, [selectedTripId]: value };
    setTripCurrencies(next);
    localStorage.setItem("tripwise_trip_currencies", JSON.stringify(next));
  }

  async function onCreatePublicSummaryLink() {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      const result = await fetchJson<{ url: string }>("/reports/public/summary-link", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          actor_identifier: actorIdentifier.trim(),
        }),
      });
      const root = (typeof window !== "undefined" ? window.location.origin : "");
      setPublicSummaryLink(`${root}${result.url}`);
      setNotice("Public read-only summary link created.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to create public link.");
    } finally {
      setLoading(false);
    }
  }

  async function onRaiseDispute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }
    if (!disputeExpenseId) {
      setError("Select an expense to dispute.");
      return;
    }
    if (disputeComment.trim().length < 5) {
      setError("Dispute comment must be at least 5 characters.");
      return;
    }

    const amountValue = disputeAmount.trim() ? Number(disputeAmount) : undefined;
    if (amountValue !== undefined && (Number.isNaN(amountValue) || amountValue <= 0)) {
      setError("Disputed amount must be greater than 0.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      await fetchJson("/disputes/", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          expense_id: disputeExpenseId,
          actor_identifier: actorIdentifier.trim(),
          comment: disputeComment.trim(),
          disputed_amount: amountValue,
        }),
      });
      setDisputeComment("");
      setDisputeAmount("");
      await loadTripDetails(selectedTripId);
      setNotice("Dispute raised.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to raise dispute.");
    } finally {
      setLoading(false);
    }
  }

  async function onSetDisputeState(disputeId: string, action: "review" | "resolve") {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");

      if (action === "review") {
        await fetchJson(`/disputes/${disputeId}/review`, {
          method: "POST",
          body: JSON.stringify({
            admin_identifier: actorIdentifier.trim(),
            note: "Marked under review from dashboard",
          }),
        });
      } else {
        const note = resolveCommentById[disputeId]?.trim() ?? "Resolved from dashboard";
        if (note.length < 3) {
          setError("Resolution comment must be at least 3 characters.");
          setLoading(false);
          return;
        }
        await fetchJson(`/disputes/${disputeId}/resolve`, {
          method: "POST",
          body: JSON.stringify({
            admin_identifier: actorIdentifier.trim(),
            resolution_comment: note,
          }),
        });
      }

      await loadTripDetails(selectedTripId);
      setNotice(action === "review" ? "Dispute moved to in-review." : "Dispute resolved.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update dispute.");
    } finally {
      setLoading(false);
    }
  }

  async function onCreateTrip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tripName.trim()) {
      setError("Trip name cannot be empty.");
      return;
    }

    const drafts = memberDrafts.map((entry) => ({
      name: entry.name.trim(),
      email: entry.email.trim(),
      registered: entry.registered,
    }));

    if (createMode === "self") {
      if (drafts.some((entry) => !entry.name)) {
        setError("Please provide names for all members.");
        return;
      }
    } else {
      if (drafts.some((entry) => !entry.name || !entry.email)) {
        setError("Please provide name and email for all members.");
        return;
      }
    }

    try {
      setLoading(true);
      setError("");
      const response = await fetchJson<{ trip: Trip }>("/trips/", {
        method: "POST",
        body: JSON.stringify({
          name: tripName.trim(),
          creator_identifier: actorIdentifier.trim(),
          creation_mode: createMode,
          member_entries: drafts.map((entry) => ({
            name: entry.name,
            email: createMode === "dynamic" ? entry.email : "",
          })),
        }),
      });
      setTripName("");
      setNewTripMemberCount(1);
      setMemberDrafts([{ name: "", email: "", registered: null }]);
      await loadTrips();
      if (response.trip?.trip_id) {
        setSelectedTripId(response.trip.trip_id);
        await loadTripDetails(response.trip.trip_id);
      }
      setNotice(createMode === "self" ? "Trip created for admin-only work (no invites sent)." : "Trip created and invites sent to registered members.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to create trip.");
    } finally {
      setLoading(false);
    }
  }

  async function checkMemberStatus(index: number) {
    const email = memberDrafts[index]?.email?.trim();
    if (!email) {
      return;
    }
    try {
      const result = await fetchJson<{ registered: boolean }>("/auth/identifier/status", {
        method: "POST",
        body: JSON.stringify({ identifier: email }),
      });
      setMemberDrafts((current) => {
        const next = [...current];
        if (next[index]) {
          next[index] = { ...next[index], registered: result.registered };
        }
        return next;
      });
    } catch {
      setMemberDrafts((current) => {
        const next = [...current];
        if (next[index]) {
          next[index] = { ...next[index], registered: null };
        }
        return next;
      });
    }
  }

  async function onTripLifecycle(action: "close" | "archive") {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson(`/trips/${selectedTripId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ actor_identifier: actorIdentifier.trim() }),
      });
      await loadTrips();
      await loadTripDetails(selectedTripId);
      setNotice(action === "close" ? "Trip closed." : "Trip archived.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Failed to ${action} trip.`);
    } finally {
      setLoading(false);
    }
  }

  async function onReviewExpense(expenseId: string, action: "approve" | "reject") {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson(`/expenses/${expenseId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ admin_identifier: actorIdentifier.trim() }),
      });
      await loadTripDetails(selectedTripId);
      setNotice(`Expense ${action}d.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Failed to ${action} expense.`);
    } finally {
      setLoading(false);
    }
  }

  async function onGenerateReport() {
    if (!selectedTripId) {
      setError("Select a trip first.");
      return;
    }

    const recipients = reportEmailsCsv
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    try {
      setLoading(true);
      setError("");
      await fetchJson("/reports/generate", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          actor_identifier: actorIdentifier.trim(),
          report_type: reportType,
          format: reportFormat,
          email_to: recipients,
        }),
      });
      await loadTripDetails(selectedTripId);
      setNotice("Report generated.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Report generation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onMarkPaid(row: SettlementRow) {
    if (!selectedTripId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      await fetchJson("/payments/mark-paid", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTripId,
          actor_identifier: actorIdentifier.trim(),
          from_member_id: row.fromMemberId,
          to_member_id: row.toMemberId,
          amount: row.amount,
          method: payMethod,
        }),
      });
      await loadTripDetails(selectedTripId);
      setNotice("Payment marked as paid.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to mark payment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <div className="dashboard-backdrop" aria-hidden="true" />
      <section className="dashboard-panel">
        <header className="dashboard-header">
          <div>
            <p className="dashboard-eyebrow">The Master Ledger</p>
            <h1>Live Operations</h1>
            <p className="dashboard-subcopy">A panoptic view of expenses, perfectly coordinated splits, and precise resolution.</p>
          </div>
          <div className="row-actions">
            <button className="tw-btn tw-btn-muted" disabled={loading} onClick={() => void loadTrips()}>
              {loading ? "Loading..." : "Refresh"}
            </button>
            <button className="tw-btn" onClick={openExpenseComposer} disabled={loading || !selectedTripId}>
              Add Expense
            </button>
          </div>
        </header>

        <section className="dashboard-grid-top">
          <article className="stat-card"><span>Trips</span><strong>{trips.length}</strong></article>
          <article className="stat-card"><span>Total Members</span><strong>{selectedTrip?.member_count ?? 0}</strong></article>
          <article className="stat-card"><span>Accepted Members</span><strong>{acceptedMemberCount}</strong></article>
          <article className="stat-card"><span>Pending Approvals</span><strong>{pendingExpenses.length}</strong></article>
          <article className="stat-card"><span>Disputes</span><strong>{disputes.length}</strong></article>
        </section>
        <section className="widget-card">
          <h2>Reminder Nudges</h2>
          <p className="empty-copy">
            Pending approvals: {pendingExpenses.length} | Unpaid settlements: {settlementRows.length}
          </p>
        </section>

        <section className="dashboard-grid-main">
          <div className="column-stack">
            <article className="widget-card">
              <h2>Session</h2>
              <p className="empty-copy">
                Logged in as: <strong>{sessionProfile.name || sessionProfile.nickname || "TripWise User"}</strong>
              </p>
              <p className="empty-copy">Email: {actorIdentifier || "-"}</p>
              <div className="row-actions top-gap">
                <button className="tw-btn tw-btn-muted" disabled={loading} onClick={() => void loadTrips()}>
                  Load Trips
                </button>
                <button className="tw-btn" type="button" onClick={openProfileEditor} disabled={loading}>
                  Edit Details
                </button>
              </div>
            </article>

            <article className="widget-card">
              <h2>Create Trip</h2>
              <form onSubmit={onCreateTrip} className="stack-form">
                <label className="field-label">Trip Name</label>
                <input className="tw-input" value={tripName} onChange={(event) => setTripName(event.target.value)} placeholder="Goa Sprint" />
                <label className="field-label">Add Members Mode</label>
                <select
                  className="tw-input"
                  aria-label="Add members mode"
                  value={createMode}
                  onChange={(event) => setCreateMode(event.target.value as CreateMode)}
                >
                  <option value="self">Add Only For Myself</option>
                  <option value="dynamic">Add Dynamic</option>
                </select>
                <label className="field-label">Number of Members</label>
                <input
                  className="tw-input"
                  aria-label="Number of members"
                  type="number"
                  min={1}
                  max={20}
                  value={newTripMemberCount}
                  onChange={(event) => {
                    const count = Math.max(1, Math.min(20, Number(event.target.value) || 1));
                    setNewTripMemberCount(count);
                    setMemberDrafts((current) => {
                      if (current.length === count) {
                        return current;
                      }
                      if (current.length < count) {
                        return [...current, ...Array.from({ length: count - current.length }, () => ({ name: "", email: "", registered: null }))];
                      }
                      return current.slice(0, count);
                    });
                  }}
                />
                <label className="field-label">Member Details</label>
                {memberDrafts.map((draft, index) => (
                  <div key={`dashboard-member-${index}`} className="stack-form">
                    <input
                      className="tw-input"
                      value={draft.name}
                      onChange={(event) =>
                        setMemberDrafts((current) => {
                          const next = [...current];
                          next[index] = { ...next[index], name: event.target.value };
                          return next;
                        })
                      }
                      placeholder={`Member ${index + 1} name`}
                    />
                    {createMode === "dynamic" ? (
                      <>
                        <input
                          className="tw-input"
                          value={draft.email}
                          onChange={(event) =>
                            setMemberDrafts((current) => {
                              const next = [...current];
                              next[index] = { ...next[index], email: event.target.value, registered: null };
                              return next;
                            })
                          }
                          onBlur={() => void checkMemberStatus(index)}
                          placeholder={`Member ${index + 1} email`}
                        />
                        <p className="empty-copy">
                          {draft.registered === null ? "Account status: check email" : draft.registered ? "This member has account" : "This member does not exist yet"}
                        </p>
                      </>
                    ) : null}
                  </div>
                ))}
                <button className="tw-btn" disabled={loading} type="submit">
                  {createMode === "self" ? "Create Trip (No Invites)" : "Create Trip and Send Invites"}
                </button>
              </form>
            </article>

            <article className="widget-card">
              <h2>Trips</h2>
              <div className="trip-list">
                {trips.length === 0 ? <p className="empty-copy">No trips yet.</p> : null}
                {trips.map((trip) => (
                  <button
                    key={trip.trip_id}
                    className={`trip-chip ${selectedTripId === trip.trip_id ? "active" : ""}`}
                    onClick={() => {
                      setSelectedTripId(trip.trip_id);
                      void loadTripDetails(trip.trip_id);
                    }}
                  >
                    <span>{trip.name}</span>
                    <small>{trip.status} | members: {trip.member_count} | role: {uiRoleLabel(trip.my_role)}</small>
                  </button>
                ))}
              </div>
            </article>

            <article className="widget-card">
              <h2>Trip Lifecycle</h2>
              <label className="field-label">Trip Currency</label>
              <select className="tw-input" value={currentCurrency} onChange={(event) => onChangeTripCurrency(event.target.value)} title="Trip currency" aria-label="Trip currency">
                {CURRENCIES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <div className="row-actions row-actions-wrap">
                <button className="tw-btn tw-btn-small" onClick={() => void onTripLifecycle("close")} disabled={!selectedTripId || loading}>
                  Close Trip
                </button>
                <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => void onTripLifecycle("archive")} disabled={!selectedTripId || loading}>
                  Archive Trip
                </button>
              </div>
            </article>

            <article className="widget-card">
                    <div>
                      <label>My Role</label>
                      <p>{uiRoleLabel(selectedTrip?.my_role)}</p>
                    </div>
              <h2>Members</h2>
              {members.length === 0 ? <p className="empty-copy">No members loaded.</p> : null}
              {members.map((member) => (
                <div key={member.memberId} className="row-card row-card-stack">
                  <div>
                    <strong>{memberLabel(member)}</strong>
                    <p>{member.role} | {member.inviteStatus}</p>
                  </div>
                </div>
              ))}
            </article>
            <article className="widget-card">
              <h2>Quick Add Expense</h2>
              <form className="stack-form" onSubmit={onQuickAddExpense}>
                <input className="tw-input" value={quickAddReason} onChange={(event) => setQuickAddReason(event.target.value)} placeholder="Reason" />
                <input className="tw-input" value={quickAddAmount} onChange={(event) => setQuickAddAmount(event.target.value)} placeholder="Amount" />
                <select className="tw-input" value={quickAddPayerId} onChange={(event) => setQuickAddPayerId(event.target.value)} title="Quick add payer" aria-label="Quick add payer">
                  <option value="">Select payer</option>
                  {acceptedEditableMembers.map((member) => (
                    <option key={member.memberId} value={member.memberId}>{memberLabel(member)}</option>
                  ))}
                </select>
                <button className="tw-btn" type="submit" disabled={loading}>Quick Add</button>
              </form>
            </article>
          </div>

          <div className="column-stack wide">
            <article className="widget-card">
              <h2>Live Expense Ledger</h2>
              <p className="empty-copy">Excel-style live sheet of trip expenses with running total.</p>
              <div className="ledger-sheet-wrap">
                <table className="ledger-sheet" aria-label="Live expense ledger">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Status</th>
                      <th>Split</th>
                      <th>Amount</th>
                      <th>Running Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {liveLedgerRows.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="ledger-empty">No expenses yet for this trip.</td>
                      </tr>
                    ) : null}
                    {liveLedgerRows.map((row, index) => (
                      <tr key={row.expenseId}>
                        <td>{index + 1}</td>
                        <td>{new Date(row.createdAt).toLocaleDateString()}</td>
                        <td>{row.description}</td>
                        <td>{row.status}</td>
                        <td>{row.splitType}</td>
                        <td>{formatMoney(row.amount)}</td>
                        <td>{formatMoney(row.runningTotal)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="widget-card">
              <h2>Pending Expense Approvals</h2>
              {pendingExpenses.length === 0 ? <p className="empty-copy">No pending expenses.</p> : null}
              {pendingExpenses.map((expense) => (
                <div key={expense.expense_id} className="row-card">
                  <div>
                    <strong>{expense.description}</strong>
                    <p>{formatMoney(expense.amount)}</p>
                  </div>
                  <div className="row-actions">
                    <button className="tw-btn tw-btn-small" onClick={() => void onReviewExpense(expense.expense_id, "approve")}>Approve</button>
                    <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => void onReviewExpense(expense.expense_id, "reject")}>Reject</button>
                  </div>
                </div>
              ))}
            </article>

            <article className="widget-card">
              <h2>Disputes</h2>
              <form className="stack-form" onSubmit={onRaiseDispute}>
                <select className="tw-input" value={disputeExpenseId} onChange={(event) => setDisputeExpenseId(event.target.value)} title="Dispute expense" aria-label="Dispute expense">
                  <option value="">Select expense</option>
                  {expenses.map((expense) => (
                    <option key={expense.expense_id} value={expense.expense_id}>
                      {expense.description} - Rs {expense.amount.toFixed(2)} ({expense.status})
                    </option>
                  ))}
                </select>
                <input className="tw-input" value={disputeAmount} onChange={(event) => setDisputeAmount(event.target.value)} placeholder="Disputed amount (optional)" />
                <textarea className="tw-input" value={disputeComment} onChange={(event) => setDisputeComment(event.target.value)} rows={3} placeholder="Comment" />
                <button className="tw-btn" type="submit" disabled={!selectedTripId || loading}>Raise Dispute</button>
              </form>

              {disputes.map((dispute) => (
                <div key={dispute.dispute_id} className="row-card row-card-stack">
                  <div>
                    <strong>{dispute.status.toUpperCase()} - {dispute.expense_id.slice(0, 8)}</strong>
                    <p>{dispute.comment}</p>
                  </div>
                  <div className="row-actions row-actions-wrap">
                    <button className="tw-btn tw-btn-small tw-btn-muted" onClick={() => void onSetDisputeState(dispute.dispute_id, "review")}>Mark In Review</button>
                    <input
                      className="tw-input compact-input"
                      placeholder="Resolution note"
                      value={resolveCommentById[dispute.dispute_id] ?? ""}
                      onChange={(event) =>
                        setResolveCommentById((current) => ({
                          ...current,
                          [dispute.dispute_id]: event.target.value,
                        }))
                      }
                    />
                    <button className="tw-btn tw-btn-small" onClick={() => void onSetDisputeState(dispute.dispute_id, "resolve")}>Resolve</button>
                  </div>
                </div>
              ))}
            </article>

            <article className="widget-card">
              <h2>Settlement</h2>
              <select className="tw-input" value={payMethod} onChange={(event) => setPayMethod(event.target.value)} title="Payment method" aria-label="Payment method">
                <option value="manual">manual</option>
                <option value="bank">bank</option>
                <option value="cash">cash</option>
              </select>
              {settlementRows.length === 0 ? <p className="empty-copy">No outstanding transfers.</p> : null}
              {settlementRows.map((row, index) => (
                <div key={`${row.fromMemberId}-${row.toMemberId}-${index}`} className="row-card">
                  <div>
                    <strong>{row.fromMemberId.slice(0, 8)} {"->"} {row.toMemberId.slice(0, 8)}</strong>
                    <p>{formatMoney(row.amount)}</p>
                  </div>
                  <button className="tw-btn tw-btn-small" onClick={() => void onMarkPaid(row)}>Mark Paid</button>
                </div>
              ))}
            </article>

            <article className="widget-card">
              <h2>Reports</h2>
              <div className="inline-grid">
                <select className="tw-input" value={reportType} onChange={(event) => setReportType(event.target.value)} title="Report type" aria-label="Report type">
                  <option value="summary">summary</option>
                  <option value="detailed">detailed</option>
                  <option value="settlement">settlement</option>
                  <option value="expense_breakdown">expense_breakdown</option>
                </select>
                <select className="tw-input" value={reportFormat} onChange={(event) => setReportFormat(event.target.value)} title="Report format" aria-label="Report format">
                  <option value="pdf">pdf</option>
                  <option value="excel">excel</option>
                  <option value="json">json</option>
                </select>
              </div>
              <input className="tw-input" value={reportEmailsCsv} onChange={(event) => setReportEmailsCsv(event.target.value)} placeholder="Email recipients (comma separated)" />
              <button className="tw-btn" onClick={() => void onGenerateReport()} disabled={!selectedTripId}>Generate Report</button>
              <button className="tw-btn tw-btn-muted" onClick={() => void onCreatePublicSummaryLink()} disabled={!selectedTripId || loading}>Create Read-only Share Link</button>
              {publicSummaryLink ? <p className="empty-copy">{publicSummaryLink}</p> : null}
              <div className="reports-list">
                {reports.length === 0 ? <p className="empty-copy">No reports generated yet.</p> : null}
                {reports.map((report) => (
                  <div key={report.report_id} className="row-card">
                    <div>
                      <strong>{report.report_type} ({report.format})</strong>
                      <p>{new Date(report.created_at).toLocaleString()}</p>
                    </div>
                    <a className="tw-btn tw-btn-small tw-btn-muted" href={report.file_url} target="_blank" rel="noreferrer">Download</a>
                  </div>
                ))}
              </div>
            </article>

            <article className="widget-card">
              <h2>In-App Notifications</h2>
              {notifications.length === 0 ? <p className="empty-copy">No notifications yet.</p> : null}
              {notifications.map((item) => (
                <div key={item.notification_id} className="row-card row-card-stack">
                  <div>
                    <strong>{item.payload?.title ?? item.event_type}</strong>
                    <p>{item.payload?.message ?? "Update received."}</p>
                    <p>{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </article>
          </div>
        </section>

        {error ? <p className="flash flash-error">{error}</p> : null}
        {notice ? <p className="flash flash-ok">{notice}</p> : null}
      </section>

      {profileModalOpen ? (
        <div className="expense-modal-backdrop" role="presentation" onClick={closeProfileEditor}>
          <section className="expense-modal" role="dialog" aria-modal="true" aria-labelledby="profile-editor-title" onClick={(event) => event.stopPropagation()}>
            <h3 id="profile-editor-title">Edit Details</h3>
            <p className="empty-copy">
              Update your profile information here. If you change your email, TripWise will send a verification code to the new address before saving.
            </p>
            <form
              className="stack-form top-gap"
              onSubmit={(event) => {
                event.preventDefault();
                void saveProfileDetails();
              }}
            >
              <label className="field-label" htmlFor="profile-name">Full name</label>
              <input id="profile-name" className="tw-input" value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Full name" />

              <label className="field-label" htmlFor="profile-nickname">Nickname</label>
              <input id="profile-nickname" className="tw-input" value={profileNickname} onChange={(event) => setProfileNickname(event.target.value)} placeholder="Nickname" />

              <label className="field-label" htmlFor="profile-email">Email</label>
              <input id="profile-email" className="tw-input" type="email" value={profileEmail} onChange={(event) => setProfileEmail(event.target.value)} placeholder="Email" />
              <p className="field-help">Change the email, then send an OTP to the new address before saving.</p>

              <label className="field-label" htmlFor="profile-phone">Phone</label>
              <input id="profile-phone" className="tw-input" type="tel" value={profilePhone} onChange={(event) => setProfilePhone(event.target.value)} placeholder="Phone" />

              <div className="inline-grid">
                <div>
                  <label className="field-label" htmlFor="profile-upi-id">UPI ID</label>
                  <input id="profile-upi-id" className="tw-input" value={profileUpiId} onChange={(event) => setProfileUpiId(event.target.value)} placeholder="UPI ID" />
                </div>
                <div>
                  <label className="field-label" htmlFor="profile-upi-number">UPI Number</label>
                  <input id="profile-upi-number" className="tw-input" value={profileUpiNumber} onChange={(event) => setProfileUpiNumber(event.target.value)} placeholder="UPI Number" />
                </div>
              </div>

              {profileEmail.trim() && profileEmail.trim() !== (sessionProfile.email ?? "").trim() ? (
                <>
                  <label className="field-label" htmlFor="profile-email-otp">Email OTP</label>
                  <input
                    id="profile-email-otp"
                    className="tw-input"
                    value={profileEmailOtp}
                    onChange={(event) => setProfileEmailOtp(event.target.value)}
                    placeholder="Enter email OTP"
                    maxLength={6}
                    inputMode="numeric"
                  />
                  <p className="field-help">Request a verification code before saving the new email.</p>
                </>
              ) : null}

              <div className="expense-modal-footer">
                <button className="tw-btn tw-btn-muted" type="button" onClick={closeProfileEditor} disabled={profileSaving}>
                  Cancel
                </button>
                {profileEmail.trim() && profileEmail.trim() !== (sessionProfile.email ?? "").trim() ? (
                  <button className="tw-btn tw-btn-muted" type="button" onClick={() => void requestEmailChangeOtp()} disabled={profileSaving}>
                    Send Email OTP
                  </button>
                ) : null}
                <button className="tw-btn" type="submit" disabled={profileSaving || !profilePhone.trim()}>
                  {profileSaving ? "Saving..." : "Save Changes"}
                </button>
              </div>
              {profileEmailOtpRequested ? <p className="empty-copy">Code sent to the new email address.</p> : null}
            </form>
          </section>
        </div>
      ) : null}

      {expenseModalOpen ? (
        <div className="expense-modal-backdrop" role="dialog" aria-modal="true" aria-label="Advanced expense composer">
          <form className="expense-modal" onSubmit={submitAdvancedExpense}>
            <h3>Advanced Expense Composer</h3>
            <p className="empty-copy">Supports multi-payer + equal/dutch/percentage/selective/custom allocations.</p>
            <label className="field-label">Template</label>
            <select
              className="tw-input"
              value={selectedTemplate}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedTemplate(value);
                if (!value) return;
                const preset = EXPENSE_TEMPLATES.find((item) => item.label === value);
                if (preset) {
                  setExpenseDescription(preset.description);
                }
              }}
              title="Expense template"
              aria-label="Expense template"
            >
              <option value="">Select template</option>
              {EXPENSE_TEMPLATES.map((item) => <option key={item.label} value={item.label}>{item.label}</option>)}
            </select>

            <section className={`section-box composer-trip-box ${hasTripSelection ? "" : "composer-trip-warning"}`.trim()}>
              <label className="field-label">Selected Trip</label>
              <p className="empty-copy">
                {selectedTrip ? `${selectedTrip.name} (${selectedTrip.status})` : "No trip selected"}
              </p>
              {!hasTripSelection ? (
                <p className="composer-warning-copy">
                  Please choose a trip before creating this expense.
                </p>
              ) : null}
              {trips.length > 1 ? (
                <>
                  <p className="empty-copy">Multiple trips are available. Choose any one trip before saving this expense.</p>
                  <select
                    className="tw-input"
                    value={selectedTripId}
                    onChange={(event) => {
                      const nextTripId = event.target.value;
                      setSelectedTripId(nextTripId);
                      void loadTripDetails(nextTripId);
                    }}
                    title="Composer trip selection"
                    aria-label="Composer trip selection"
                    disabled={loading}
                  >
                    <option value="">Select a trip</option>
                    {trips.map((trip) => (
                      <option key={trip.trip_id} value={trip.trip_id}>
                        {trip.name} ({trip.status})
                      </option>
                    ))}
                  </select>
                </>
              ) : null}
            </section>

            <div className="expense-grid">
              <section className="section-box">
                <label className="field-label">Description</label>
                <input className="tw-input" value={expenseDescription} onChange={(event) => setExpenseDescription(event.target.value)} placeholder="Airport cab and toll" />
                <label className="field-label">Total Amount</label>
                <input
                  className="tw-input"
                  value={expenseAmount}
                  onChange={(event) => setExpenseAmount(event.target.value)}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  title="Expense amount"
                  aria-label="Expense amount"
                />
                <label className="field-label">Split Strategy</label>
                <select className="tw-input" value={splitPreset} onChange={(event) => setSplitPreset(event.target.value as SplitPreset)} title="Split strategy" aria-label="Split strategy">
                  <option value="equal">Equal</option>
                  <option value="dutch">Dutch (manual amount per member)</option>
                  <option value="percentage">Percentage</option>
                  <option value="selective">Selective</option>
                  <option value="custom">Custom (manual allocations)</option>
                </select>
              </section>

              <section className="section-box">
                <div className="row-actions">
                  <h4>Paid By</h4>
                  <button type="button" className="tw-btn tw-btn-small tw-btn-muted" onClick={addPayerRow}>Add Payer</button>
                </div>
                {payerDrafts.map((payer, index) => (
                  <div key={`${payer.memberId}-${index}`} className="split-row">
                    <select
                      className="tw-input"
                      value={payer.memberId}
                      title="Payer member"
                      aria-label="Payer member"
                      onChange={(event) =>
                        setPayerDrafts((current) =>
                          current.map((item, idx) => (idx === index ? { ...item, memberId: event.target.value } : item)),
                        )
                      }
                    >
                      {acceptedEditableMembers.map((member) => (
                        <option key={member.memberId} value={member.memberId}>{memberLabel(member)}</option>
                      ))}
                    </select>
                    <input
                      className="tw-input"
                      value={payer.amountPaid}
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="0.00"
                      title="Payer amount"
                      aria-label="Payer amount"
                      readOnly={index === payerDrafts.length - 1}
                      onChange={(event) =>
                        setPayerDrafts((current) =>
                          current.map((item, idx) => (idx === index ? { ...item, amountPaid: event.target.value } : item)),
                        )
                      }
                    />
                    {index === payerDrafts.length - 1 ? <span className="auto-balance-tag">Auto</span> : null}
                    <button type="button" className="tw-btn tw-btn-small tw-btn-muted" onClick={() => removePayerRow(index)}>
                      Remove
                    </button>
                  </div>
                ))}
                <p className="empty-copy">Paid Total: {formatMoney(toMoney(payerTotal))} / {formatMoney(toMoney(parseMoney(expenseAmount)))}</p>
              </section>
            </div>

            <section className="section-box">
              <h4>Split Allocation</h4>
              {splitDrafts.map((split, index) => {
                const member = acceptedEditableMembers.find((m) => m.memberId === split.memberId);
                return (
                  <div key={split.memberId} className="split-row">
                    <div className="pill-toggle">
                      <input
                        type="checkbox"
                        title="Include participant"
                        aria-label="Include participant"
                        checked={split.include}
                        onChange={(event) =>
                          setSplitDrafts((current) =>
                            current.map((item, idx) => (idx === index ? { ...item, include: event.target.checked } : item)),
                          )
                        }
                      />
                      <span>{member ? memberLabel(member) : split.memberId}</span>
                    </div>
                    <input
                      className="tw-input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Amount"
                      title="Amount owed"
                      aria-label="Amount owed"
                      disabled={splitPreset === "percentage" || !split.include || index === autoBalancedSplitIndex}
                      value={split.amountOwed}
                      onChange={(event) =>
                        setSplitDrafts((current) =>
                          current.map((item, idx) => (idx === index ? { ...item, amountOwed: event.target.value } : item)),
                        )
                      }
                    />
                    {index === autoBalancedSplitIndex ? <span className="auto-balance-tag">Auto</span> : null}
                    <input
                      className="tw-input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="%"
                      title="Percentage"
                      aria-label="Percentage"
                      disabled={splitPreset !== "percentage" || !split.include}
                      value={split.percentage}
                      onChange={(event) =>
                        setSplitDrafts((current) =>
                          current.map((item, idx) => (idx === index ? { ...item, percentage: event.target.value } : item)),
                        )
                      }
                    />
                  </div>
                );
              })}
              {(splitPreset === "dutch" || splitPreset === "custom" || splitPreset === "selective") ? (
                <p className="empty-copy">Allocated Total: {formatMoney(toMoney(splitAmountTotal))} / {formatMoney(toMoney(parseMoney(expenseAmount)))}</p>
              ) : null}
            </section>

            <div className="expense-modal-footer">
              <button type="button" className="tw-btn tw-btn-muted" onClick={() => setExpenseModalOpen(false)}>Cancel</button>
              <button type="submit" className="tw-btn" disabled={loading}>Save Expense</button>
            </div>
          </form>
        </div>
      ) : null}
    </main>
  );
}
