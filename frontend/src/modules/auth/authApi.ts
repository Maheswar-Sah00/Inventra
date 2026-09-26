import { apiRequest } from "../../services/apiClient";
import type { MessageResponse, SignupPayload, TokenResponse, User, VerifyOtpResponse } from "./types";

export const authApi = {
  signup: (payload: SignupPayload) => apiRequest<User>("/auth/signup", { method: "POST", body: payload, auth: false }),

  login: (email: string, password: string) =>
    apiRequest<TokenResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false }),

  logout: () => apiRequest<MessageResponse>("/auth/logout", { method: "POST" }),

  me: (signal?: AbortSignal) => apiRequest<User>("/auth/me", { signal }),

  forgotPassword: (email: string) =>
    apiRequest<MessageResponse>("/auth/forgot-password", { method: "POST", body: { email }, auth: false }),

  verifyOtp: (email: string, otp: string) =>
    apiRequest<VerifyOtpResponse>("/auth/verify-otp", { method: "POST", body: { email, otp }, auth: false }),

  resetPassword: (resetToken: string, password: string, confirmPassword: string) =>
    apiRequest<MessageResponse>("/auth/reset-password", {
      method: "POST",
      body: { reset_token: resetToken, password, confirm_password: confirmPassword },
      auth: false,
    }),

  updateProfile: (data: { name: string }) => apiRequest<User>("/users/me", { method: "PATCH", body: data }),
};
