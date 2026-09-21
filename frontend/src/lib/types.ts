export interface Account {
  id: number;
  customer_id: number;
  account_type: string;
  balance: string;
  status: string;
  created_at: string;
}

export interface Transaction {
  id: number;
  account_id: number;
  amount: string;
  transaction_type: string;
  channel: string;
  merchant_name: string;
  merchant_category: string;
  city: string;
  country: string;
  occurred_at: string;
  is_fraud: boolean;
}

export interface FraudFlag {
  id: number;
  transaction_id: number;
  fraud_score: number;
  model_version: string;
  status: string;
  created_at: string;
  reviewed_at: string | null;
}

export interface FlaggedTransaction {
  flag: FraudFlag;
  transaction: Transaction;
}

export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface FeatureContribution {
  feature: string;
  value: number;
  contribution: number;
  direction: string;
}

export interface FlagExplanation {
  flag_id: number;
  transaction_id: number;
  fraud_score: number;
  model_version: string;
  baseline_score: number;
  top_contributions: FeatureContribution[];
}

export interface PendingAction {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
}

export interface ChatResponse {
  thread_id: string;
  reply: string | null;
  awaiting_approval: boolean;
  reason: string | null;
  actions: PendingAction[];
}

export interface User {
  username: string;
  role: string;
}