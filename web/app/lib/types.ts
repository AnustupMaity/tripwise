/* ──────────────────────────────────────────────────────────
 * Shared types used by multiple pages / components.
 * Import from here instead of re-declaring per file.
 * ────────────────────────────────────────────────────────── */

export type Trip = {
  trip_id: string;
  name: string;
  status: string;
  member_count: number;
  my_role?: string;
};

export type Member = {
  memberId: string;
  role: string;
  inviteStatus: "pending" | "accepted" | "rejected" | string;
  canEdit: boolean;
  identifier: string | null;
};

export type PendingExpense = {
  expense_id: string;
  description: string;
  amount: number;
  status: string;
};

export type ExpenseItem = {
  expense_id: string;
  description: string;
  amount: number;
  status: string;
  split_type: string;
  created_at: string;
};

export type DisputeItem = {
  dispute_id: string;
  expense_id: string;
  status: string;
  comment: string;
  disputed_amount: number | null;
  created_at: string;
};

export type SettlementRow = {
  fromMemberId: string;
  toMemberId: string;
  amount: number;
};

export type ReportItem = {
  report_id: string;
  report_type: string;
  format: string;
  file_url: string;
  created_at: string;
  emailed_to?: string[];
};

export type InAppNotification = {
  notification_id: string;
  event_type: string;
  payload: {
    title?: string;
    message?: string;
    tripId?: string;
  };
  created_at: string;
};

export type SessionProfile = {
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  upiId?: string | null;
  upiNumber?: string | null;
};

export type CreateMode = "self" | "dynamic";

export type MemberDraft = {
  name: string;
  email: string;
  registered: boolean | null;
};

export type PayerDraft = {
  memberId: string;
  amountPaid: string;
};

export type SplitDraft = {
  memberId: string;
  include: boolean;
  amountOwed: string;
  percentage: string;
};

export type SplitPreset = "equal" | "dutch" | "percentage" | "selective" | "custom";

export type LedgerRow = {
  expenseId: string;
  createdAt: string;
  description: string;
  status: string;
  splitType: string;
  amount: number;
  runningTotal: number;
};

export type ExpenseTemplate = { label: string; description: string };
