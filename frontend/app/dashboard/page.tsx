import { auth } from "@/lib/auth";
import { ShieldCheck } from "lucide-react";

export default async function DashboardPage() {
  const session = await auth();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back{session?.user?.name ? `, ${session.user.name}` : ""}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Here&apos;s your site safety overview
        </p>
      </div>

      {/* Placeholder — Phase 3 fills this with real Recharts data */}
      <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 py-24 text-center">
        <ShieldCheck className="h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-500">
          Dashboard analytics coming in Phase 3
        </p>
        <p className="text-xs text-gray-400">
          Add a site and camera to start monitoring
        </p>
      </div>
    </div>
  );
}
