import { NavLink } from "react-router-dom";
import { CloudUpload, LayoutGrid, LayoutDashboard, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  to: string;
  icon: typeof LayoutDashboard;
  comingSoon?: boolean;
}

const navItems: NavItem[] = [
  {
    label: "Dashboard",
    to: "/",
    icon: LayoutDashboard,
  },
  {
    label: "Template Library",
    to: "/templates",
    icon: LayoutGrid,
  },
  {
    label: "Upload Template",
    to: "/upload-template",
    icon: CloudUpload,
  },
  {
    label: "Profile",
    to: "/profile",
    icon: User,
  },
];

interface SidebarNavProps {
  onNavigate?: () => void;
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="mb-8 px-2">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
          TemplateOS
        </p>
        <h1 className="mt-2 text-xl font-semibold">Workspace</h1>
      </div>
      <nav className="space-y-1 text-sm font-medium text-slate-600 flex-1">
        {navItems.map((item) => (
          <div key={item.label}>
            {item.comingSoon ? (
              <div
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-slate-400 cursor-not-allowed"
                aria-label={`${item.label} (Coming soon)`}
              >
                <item.icon className="h-5 w-5" />
                <span>{item.label}</span>
                <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
                  Soon
                </span>
              </div>
            ) : (
              <NavLink
                to={item.to}
                onClick={onNavigate}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-slate-100 hover:text-slate-900",
                    isActive && "bg-slate-100 text-slate-900",
                  )
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            )}
          </div>
        ))}
      </nav>
    </div>
  );
}
