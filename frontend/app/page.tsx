import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";

/**
 * Root page — redirect authenticated users to dashboard,
 * unauthenticated users to login.
 */
export default async function RootPage() {
  const session = await auth();
  if (session) {
    redirect("/dashboard");
  } else {
    redirect("/login");
  }
}
