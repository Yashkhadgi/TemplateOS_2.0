import React, { useEffect, useState } from "react";
import { useForm, FormProvider } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, Save, AlertCircle, CheckCircle, ChevronLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import { DynamicField } from "@/components/forms/DynamicField";
import { templatesApi, documentsApi, TemplateField, Document, DocumentFormValues, ApiError } from "@/lib/api";
import { buildFormSchema } from "@/lib/validation";

export function EditDocumentPage() {
  const navigate = useNavigate();
  const { id: documentIdParam } = useParams<{ id: string }>();
  const documentId = documentIdParam ? parseInt(documentIdParam, 10) : 0;

  const [template, setTemplate] = useState<any>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const token = localStorage.getItem("templateos_access_token") || "";

  useEffect(() => {
    if (!documentId) {
      navigate("/dashboard");
      return;
    }
    async function fetchData() {
      try {
        const doc = await documentsApi.getDocument(token, documentId);
        setDocument(doc);
        const [templateData, fieldsData] = await Promise.all([
          templatesApi.getTemplateDetail(token, doc.template_id),
          templatesApi.getFields(token, doc.template_id),
        ]);
        setTemplate(templateData);
        setFields(fieldsData);
      } catch (err) {
        console.error("Failed to load document:", err);
        setSaveError("Failed to load document. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [documentId, token]);

  const schema = React.useMemo(() => buildFormSchema(fields), [fields]);
  const form = useForm<DocumentFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {},
    mode: "onBlur",
  });

  // Re-run reset when schema (fields) or document values change
  useEffect(() => {
    if (fields.length > 0 && document?.values) {
      const defaultValues: DocumentFormValues = {};
      for (const val of document.values) {
        const field = fields.find(f => f.field_name === val.field_name);
        if (field && field.field_type === "list") {
          try {
            defaultValues[val.field_name] = JSON.parse(val.value);
          } catch {
            defaultValues[val.field_name] = [val.value];
          }
        } else {
          defaultValues[val.field_name] = val.value;
        }
      }
      form.reset(defaultValues);
    }
  }, [fields, document, form]);

  const handleUpdateDraft = async (formData: DocumentFormValues) => {
    if (!documentId) return;

    setSaving(true);
    setSaveError(null);

    try {
      // Prepare values (stringify lists)
      const values = fields.map((field) => {
        const value = formData[field.field_name];
        const stringValue = Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
        return {
          field_name: field.field_name,
          value: stringValue,
        };
      });

      // Save values
      await documentsApi.saveValues(token, documentId, { values });

      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
      }, 2000);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 422 && err.detail) {
        const errors: Record<string, string> = {};
        for (const e of err.detail as Array<{ field_name: string; error: string }>) {
          errors[e.field_name] = e.error;
        }
        Object.entries(errors).forEach(([fieldName, message]) => {
          form.setError(fieldName, { message, type: "server" });
        });
      } else {
        setSaveError(err?.message || "Failed to update draft. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="h-8 bg-slate-100 rounded animate-pulse" />
        <div className="h-64 bg-slate-100 rounded animate-pulse" />
      </div>
    );
  }

  if (!document || !template) {
    return (
      <div className="mx-auto max-w-3xl text-center py-12">
        <AlertCircle className="h-12 w-12 text-slate-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900">Document not found</h2>
        <p className="mt-2 text-slate-500">The draft you're looking for doesn't exist or you don't have access to it.</p>
        <Button asChild className="mt-6">
          <a href="/dashboard">Go to Dashboard</a>
        </Button>
      </div>
    );
  }

  const groupedFields = fields.reduce((acc, field) => {
    const section = field.section || "General";
    if (!acc[section]) acc[section] = [];
    acc[section].push(field);
    return acc;
  }, {} as Record<string, TemplateField[]>);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")} className="h-8 w-8">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-bold text-slate-900">
            Editing: {document.name || `Draft ${document.id}`}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Template: {template.name} · Last saved: {new Date(document.updated_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded">
            {template.category}
          </span>
          <span className={`px-2 py-1 text-xs font-medium rounded ${
            document.status === "draft" ? "bg-yellow-100 text-yellow-700" :
            document.status === "active" ? "bg-green-100 text-green-700" :
            "bg-blue-100 text-blue-700"
          }`}>
            {document.status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Save Success Banner */}
      {saveSuccess && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className="font-medium text-green-800">Draft updated successfully!</p>
          </div>
        </div>
      )}

      {/* Save Error Banner */}
      {saveError && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <p className="text-red-800">{saveError}</p>
        </div>
      )}

      {/* Form */}
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(handleUpdateDraft)} className="space-y-6">
          <Card>
          <CardHeader>
            <CardTitle>Edit Draft</CardTitle>
            <CardDescription>
              Make changes to your draft and save to update it.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {Object.entries(groupedFields).map(([sectionName, sectionFields]) => (
              <div key={sectionName} className="space-y-4">
                {sectionName !== "General" && (
                  <div className="flex items-center gap-2">
                    <Separator />
                    <span className="px-3 py-1 text-sm font-medium text-slate-600 bg-slate-50 rounded">
                      {sectionName}
                    </span>
                    <Separator />
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  {sectionFields.map((field) => (
                    <div key={field.field_name} className={sectionFields.length === 1 ? "sm:col-span-2" : ""}>
                      <Label htmlFor={field.field_name} className="block text-sm font-medium text-slate-700 mb-1.5">
                        {field.field_label || field.field_name}
                        {field.is_required && <span className="text-red-500 ml-1">*</span>}
                      </Label>
                      <DynamicField field={field} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
          <CardFooter className="flex justify-between gap-3 border-t bg-slate-50">
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => navigate("/dashboard")} disabled={saving}>
                Back to Dashboard
              </Button>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  form.reset(form.getValues());
                  setSaveError(null);
                }}
                disabled={saving}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Reset Form
              </Button>
              <Button type="submit" disabled={saving || saveSuccess}>
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : saveSuccess ? (
                  <>
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Saved!
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Update Draft
                  </>
                )}
              </Button>
            </div>
          </CardFooter>
        </Card>
        </form>
      </FormProvider>
    </div>
  );
}