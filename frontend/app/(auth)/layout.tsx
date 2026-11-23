/**
 * Auth layout — no sidebar, centered content.
 * Logged-in users are redirected away from auth pages by middleware.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
