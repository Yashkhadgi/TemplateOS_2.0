import { useState } from "react";
import { UploadTemplateForm } from "@/components/upload/UploadTemplateForm";

export function UploadTemplatePage() {
  const [uploadPhase, setUploadPhase] = useState<"idle" | "uploading" | "done">("idle");

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="text-sm font-medium uppercase tracking-wider text-slate-500">
          V1.2 Template Library
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Upload Template</h1>
        <p className="mt-2 text-sm text-slate-600">
          Upload a DOCX file to create a reusable template.
        </p>
      </div>

      {/* 3-Step Status Strip */}
      <div className="flex items-center w-full pb-2">
        {[
          { step: 1, label: "Fill Details", phase: "idle" },
          { step: 2, label: "Uploading File", phase: "uploading" },
          { step: 3, label: "Done", phase: "done" },
        ].map((item, index, arr) => {
          const isActive = uploadPhase === item.phase;
          const isPast = arr.findIndex((x) => x.phase === uploadPhase) > index;
          const isFilled = isActive || isPast;

          return (
            <div key={item.step} className={`flex items-center ${index < arr.length - 1 ? "flex-1" : ""}`}>
              <div className="flex items-center gap-2">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors ${
                    isFilled ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {item.step}
                </div>
                <span
                  className={`hidden text-sm sm:block whitespace-nowrap ${
                    isActive ? "font-semibold text-slate-900" : "text-slate-500"
                  }`}
                >
                  {item.label}
                </span>
              </div>
              {index < arr.length - 1 && (
                <div className="mx-4 h-px w-full flex-1 bg-slate-200" />
              )}
            </div>
          );
        })}
      </div>

      <UploadTemplateForm
        onUploadStart={() => setUploadPhase("uploading")}
        onUploadSuccess={() => setUploadPhase("done")}
      />
    </div>
  );
}
