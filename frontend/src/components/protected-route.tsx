import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/context/auth-context";

function LoadingScreen() {
  return <div className="grid min-h-screen place-items-center bg-slate-100 text-slate-600">Loading…</div>;
}

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (user) return <Navigate to="/" replace />;
  return <Outlet />;
}
