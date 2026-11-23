/** Shared TypeScript types — mirrors backend Pydantic schemas. */

import type { DefaultSession } from "next-auth";

export type UserRole = "super_admin" | "company_admin" | "site_manager" | "viewer";

export type ViolationType =
  | "no_helmet"
  | "no_vest"
  | "no_gloves"
  | "no_boots"
  | "no_mask"
  | "multiple";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  company_id: string | null;
  is_active: boolean;
}

export interface Company {
  id: string;
  name: string;
  plan: "free" | "starter" | "pro" | "enterprise";
  created_at: string;
}

export interface Site {
  id: string;
  company_id: string;
  name: string;
  location: string | null;
  created_at: string;
}

export interface Camera {
  id: string;
  site_id: string;
  name: string;
  rtsp_url: string | null;
  status: "active" | "inactive" | "error";
  created_at: string;
}

export interface Violation {
  id: string;
  camera_id: string | null;
  site_id: string;
  type: ViolationType;
  confidence_score: number | null;
  snapshot_url: string | null;
  timestamp: string;
  resolved: boolean;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Extend next-auth types
declare module "next-auth" {
  interface Session {
    accessToken: string;
    user: {
      role: string;
      companyId: string;
    } & DefaultSession["user"];
  }
  interface User {
    role: string;
    companyId: string;
    accessToken: string;
    refreshToken: string;
  }
}
