import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api";

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    if (fullName.trim().length < 2) {
      setError("Please enter your full name.");
      return;
    }
    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await signup(fullName.trim(), email.trim(), password);
      navigate("/login", { replace: true, state: { signedUp: true } });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to create your account.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">TemplateOS</p>
        <h1 className="mt-2 text-2xl font-semibold">Create your account</h1>
        <p className="mt-3 text-sm text-slate-600">
          Start with a secure personal workspace. New accounts use the normal user role.
        </p>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          {[
            { label: "Full name", type: "text", value: fullName, setValue: setFullName, autoComplete: "name" },
            { label: "Email", type: "email", value: email, setValue: setEmail, autoComplete: "email" },
            { label: "Password", type: "password", value: password, setValue: setPassword, autoComplete: "new-password" },
            { label: "Confirm password", type: "password", value: confirmPassword, setValue: setConfirmPassword, autoComplete: "new-password" },
          ].map((field) => (
            <label className="block text-sm font-medium text-slate-700" key={field.label}>
              {field.label}
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                type={field.type}
                autoComplete={field.autoComplete}
                value={field.value}
                onChange={(event) => field.setValue(event.target.value)}
                minLength={field.label === "Password" ? 8 : undefined}
                required
              />
            </label>
          ))}
          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <Button className="w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Already have an account?{" "}
          <Link className="font-medium text-slate-900 underline" to="/login">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
