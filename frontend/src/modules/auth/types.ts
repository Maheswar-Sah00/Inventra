export type UserRole = "INVENTORY_MANAGER" | "WAREHOUSE_STAFF";

export const ROLE_LABELS: Record<UserRole, string> = {
  INVENTORY_MANAGER: "Inventory Manager",
  WAREHOUSE_STAFF: "Warehouse Staff",
};

export type User = {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type SignupPayload = {
  name: string;
  email: string;
  password: string;
  confirm_password: string;
  role: UserRole;
};

export type MessageResponse = { message: string };

export type VerifyOtpResponse = { reset_token: string; expires_in: number };
