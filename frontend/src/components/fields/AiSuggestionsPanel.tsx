import { useState } from "react";
import { Check, Loader2, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { ApiError, templatesApi, type FieldSuggestion } from "@/lib/api";

const TOKEN_KEY = "templateos_access_token";

type PanelStatus = "idle" | "loading" | "success" | "error";

interface AiSuggestionsPanelProps {
  templateId: number;
  /** Current field keys in the editor — used to prevent duplicate accepts. */
  existingKeys: string[];
  /** Called when the owner accepts a proposal; the parent appends it to the
   *  Phase 3 field array (it is only persisted by the existing Save all). */
  onAccept: (suggestion: FieldSuggestion) => void;
}

/**
 * AI Suggestions panel (V1.3 Phase 4 — Member 1).
 *
 * Suggestions are PROPOSALS ONLY: Accept stages them into the Phase 3 field
 * editor (parent appends via onAccept); Dismiss removes the row. Nothing is
 * saved until the owner clicks the editor's existing "Save all". If the AI
 * service is unavailable (503), a calm notice is shown and the manual editor
 * keeps working.
 */
export function AiSuggestionsPanel({
  templateId,
  existingKeys,
  onAccept,
}: AiSuggestionsPanelProps) {
  const [status, setStatus] = useState<PanelStatus>("idle");
  const [suggestions, setSuggestions] = useState<FieldSuggestion[]>([]);
  const [acceptedKeys, setAcceptedKeys] = useState<string[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [error, setError] = useState<{
    message: string;
    unavailable: boolean;
  } | null>(null);

  const isTaken = (key: string) =>
    existingKeys.includes(key) || acceptedKeys.includes(key);

  const fetchSuggestions = async () => {
    setStatus("loading");
    setError(null);
    const token = localStorage.getItem(TOKEN_KEY) ?? "";
    try {
      const response = await templatesApi.suggestFields(token, templateId);
      setSuggestions(response.suggestions);
      setAcceptedKeys([]);
      setModel(response.model);
      setStatus("success");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError({
          message: caught.message,
          unavailable: caught.status === 503,
        });
      } else {
        setError({
          message: "Could not fetch AI suggestions. Please try again.",
          unavailable: false,
        });
      }
      setStatus("error");
    }
  };

  const accept = (suggestion: FieldSuggestion) => {
    if (isTaken(suggestion.field_name)) return;
    onAccept(suggestion);
    setAcceptedKeys((keys) => [...keys, suggestion.field_name]);
    setSuggestions((rows) =>
      rows.filter((row) => row.field_name !== suggestion.field_name),
    );
  };

  const dismiss = (suggestion: FieldSuggestion) => {
    setSuggestions((rows) =>
      rows.filter((row) => row.field_name !== suggestion.field_name),
    );
  };

  const totalProposed = suggestions.length + acceptedKeys.length;

  return (
    <Card className="border-indigo-200 bg-gradient-to-b from-indigo-50/70 to-white">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-5 w-5 text-indigo-500" />
          AI field suggestions
        </CardTitle>
        <CardDescription>
          {status === "success" && model
            ? `${totalProposed} proposal${totalProposed === 1 ? "" : "s"} — review, accept what fits. Nothing is saved until you Save all.`
            : "Let AI review the document and propose fields you may have missed. You stay in control — nothing is applied automatically."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {status !== "success" && (
          <Button
            onClick={fetchSuggestions}
            disabled={status === "loading"}
            className="gap-2"
          >
            {status === "loading" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Suggest fields with AI
              </>
            )}
          </Button>
        )}

        {status === "loading" && (
          <div className="space-y-3" aria-label="Loading AI suggestions">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {status === "error" && error && (
          <div>
            {error.unavailable ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                AI suggestions aren't available right now (the AI service
                isn't configured). You can keep configuring fields manually.
              </div>
            ) : (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {error.message}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={fetchSuggestions}
            >
              Try again
            </Button>
          </div>
        )}

        {status === "success" && (
          <>
            {suggestions.length === 0 && acceptedKeys.length === 0 && (
              <p className="text-sm text-slate-600">
                No additional fields suggested — your field set looks
                complete.
              </p>
            )}

            {suggestions.length > 0 && (
              <ul className="space-y-3">
                {suggestions.map((suggestion) => {
                  const taken = isTaken(suggestion.field_name);
                  return (
                    <li
                      key={suggestion.field_name}
                      className="space-y-2 rounded-lg border border-slate-200 bg-white p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                          {`{{${suggestion.field_name}}}`}
                        </code>
                        <span className="text-sm font-medium text-slate-900">
                          {suggestion.field_label ?? suggestion.field_name}
                        </span>
                        <Badge
                          variant="outline"
                          className="shrink-0 bg-slate-50 capitalize"
                        >
                          {suggestion.field_type}
                        </Badge>
                        {suggestion.section && (
                          <Badge variant="outline" className="shrink-0">
                            {suggestion.section}
                          </Badge>
                        )}
                        {suggestion.is_required && (
                          <Badge
                            variant="outline"
                            className="shrink-0 border-red-200 bg-red-50 text-red-700"
                          >
                            required
                          </Badge>
                        )}
                      </div>
                      {suggestion.example_value && (
                        <p className="text-xs text-slate-500">
                          Example: {suggestion.example_value}
                        </p>
                      )}
                      {suggestion.reason && (
                        <p className="text-xs italic text-slate-500">
                          Why: {suggestion.reason}
                        </p>
                      )}
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="gap-1.5"
                          disabled={taken}
                          onClick={() => accept(suggestion)}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {taken ? "Already added" : "Accept"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1.5"
                          onClick={() => dismiss(suggestion)}
                        >
                          <X className="h-3.5 w-3.5" />
                          Dismiss
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {acceptedKeys.length > 0 && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                {acceptedKeys.length} suggestion
                {acceptedKeys.length > 1 ? "s" : ""} accepted — added to the
                field editor. Click <strong>Save all</strong> to keep them.
              </div>
            )}

            {suggestions.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={fetchSuggestions}
                className="gap-1.5"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Suggest again
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
