import { useAuth } from "@/context/auth-context";
import { formatRole } from "@/lib/format";
import { AvatarFallback } from "@/components/ui/avatar-fallback";

export function ProfilePage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="h-8 w-32 animate-pulse rounded-md bg-slate-200" />
        <div className="mt-8 h-96 animate-pulse rounded-2xl bg-slate-100" />
      </div>
    );
  }

  const renderField = (label: string, value: React.ReactNode) => (
    <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 sm:py-5">
      <dt className="text-sm font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900 sm:col-span-2 sm:mt-0">
        {value ?? <span className="text-slate-400">—</span>}
      </dd>
    </div>
  );

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8 flex items-center gap-6">
        <AvatarFallback name={user?.full_name} className="h-20 w-20 text-2xl" />
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{user?.full_name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {formatRole(user?.role || "")}
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-5 sm:px-6">
          <h3 className="text-base font-semibold leading-6 text-slate-900">Personal Information</h3>
          <p className="mt-1 text-sm text-slate-500">Your account details and organization context.</p>
        </div>
        <div className="px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-slate-200">
            {renderField("Email address", user?.email)}
            {renderField(
              "Role",
              <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                {formatRole(user?.role || "")}
              </span>
            )}
            {renderField("Job title", user?.job_title)}
            {renderField("Department", user?.department)}
            {renderField("Organization", user?.organization)}
            {renderField("Phone number", user?.phone)}
            {renderField("Signature status", user?.signature_path ? "Configured" : "Not configured")}
          </dl>
        </div>
      </div>

      {user?.preferences && (
        <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-5 sm:px-6">
            <h3 className="text-base font-semibold leading-6 text-slate-900">Preferences</h3>
            <p className="mt-1 text-sm text-slate-500">Application and notification settings.</p>
          </div>
          <div className="px-4 py-5 sm:p-0">
            <dl className="sm:divide-y sm:divide-slate-200">
              {renderField("Default document format", user.preferences.default_document_format?.toUpperCase())}
              {renderField("Email notifications", user.preferences.email_notifications ? "Enabled" : "Disabled")}
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
