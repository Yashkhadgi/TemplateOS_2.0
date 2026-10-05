import { useState, useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { AvatarFallback } from "@/components/ui/avatar-fallback";
import { useAuth } from "@/context/auth-context";
import { SidebarNav } from "@/components/sidebar-nav";
import { formatRole } from "@/lib/format";
import { cn } from "@/lib/utils";

export function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Close sidebar on route change
  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const getPageTitle = () => {
    if (location.pathname === "/profile") return "Profile";
    if (location.pathname === "/templates") return "My Templates";
    if (location.pathname === "/upload-template") return "Upload Template";
    return "Dashboard";
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex">
      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Drawer */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-slate-200 bg-white p-6 transition-transform duration-300 ease-in-out lg:static lg:w-64 lg:translate-x-0",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="absolute right-4 top-4 lg:hidden">
          <Button variant="outline" size="sm" onClick={() => setIsSidebarOpen(false)} className="px-2">
            <X className="h-4 w-4" />
            <span className="sr-only">Close sidebar</span>
          </Button>
        </div>
        <SidebarNav onNavigate={() => setIsSidebarOpen(false)} />
      </aside>

      {/* Main Content Area */}
      <main className="flex min-h-screen flex-1 flex-col overflow-hidden">
        {/* Navbar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              className="lg:hidden px-2"
              onClick={() => setIsSidebarOpen(true)}
            >
              <Menu className="h-4 w-4" />
              <span className="sr-only">Open sidebar</span>
            </Button>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:block">V1.1 Project Foundation</p>
              <h2 className="text-lg font-semibold">{getPageTitle()}</h2>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{formatRole(user?.role || "")}</p>
            </div>
            <AvatarFallback name={user?.full_name} className="hidden sm:flex" />
            <div className="h-6 w-px bg-slate-200 hidden sm:block"></div>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Log out
            </Button>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
