/**
 * next-auth v5 configuration.
 * Uses Credentials provider — delegates actual auth to FastAPI backend.
 */

import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const parsed = loginSchema.safeParse(credentials);
        if (!parsed.success) return null;

        try {
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/login`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(parsed.data),
            }
          );

          if (!res.ok) return null;

          const tokens = await res.json();

          // Fetch user profile with the new access token
          const profileRes = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/me`,
            { headers: { Authorization: `Bearer ${tokens.access_token}` } }
          );

          if (!profileRes.ok) return null;
          const profile = await profileRes.json();

          return {
            id: profile.id,
            email: profile.email,
            name: profile.full_name,
            role: profile.role,
            companyId: profile.company_id,
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.role = user.role;
        token.companyId = user.companyId;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.user.role = token.role as string;
      session.user.companyId = token.companyId as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: { strategy: "jwt" },
});
