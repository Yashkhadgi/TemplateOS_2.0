import React from "react";
import { Controller, ControllerRenderProps, useFormContext } from "react-hook-form";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Calendar, List, FileText, Signature, Hash, Mail } from "lucide-react";
import { ListField } from "./ListField";

interface FieldProps {
  field: {
    field_name: string;
    field_label: string | null;
    field_type: string;
    default_value: string | null;
    is_required: boolean;
    description: string | null;
    example_value: string | null;
    validation_rule: string | null;
    section: string | null;
  };
}

interface FormValues {
  [key: string]: any;
}

const fieldTypeIcons: Record<string, React.ReactNode> = {
  text: <FileText className="h-4 w-4" />,
  textarea: <FileText className="h-4 w-4" />,
  number: <Hash className="h-4 w-4" />,
  date: <Calendar className="h-4 w-4" />,
  email: <Mail className="h-4 w-4" />,
  list: <List className="h-4 w-4" />,
  signature: <Signature className="h-4 w-4" />,
};

const fieldTypeLabels: Record<string, string> = {
  text: "Text",
  textarea: "Long Text",
  number: "Number",
  date: "Date",
  email: "Email",
  list: "List",
  signature: "Signature",
};

export function DynamicField({ field }: FieldProps) {
  const { control, formState: { errors } } = useFormContext<FormValues>();
  const fieldName = field.field_name;
  const fieldError = errors[fieldName] as { message?: string } | undefined;
  const icon = fieldTypeIcons[field.field_type] || <FileText className="h-4 w-4" />;
  const typeLabel = fieldTypeLabels[field.field_type] || field.field_type;

  // Parse default value for list fields
  const getDefaultValue = () => {
    if (field.field_type === "list" && field.default_value) {
      try {
        return JSON.parse(field.default_value);
      } catch {
        return [];
      }
    }
    return field.default_value || "";
  };

  const renderInput = ({ field: controllerField }: { field: ControllerRenderProps<FormValues, string> }) => {
    const { onChange, onBlur, value, ref, disabled } = controllerField;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      onChange(e.target.value);
    };

    const commonProps = {
      id: fieldName,
      onChange: handleChange,
      onBlur,
      ref,
      disabled,
      "aria-invalid": fieldError ? true : false,
      "aria-describedby": fieldError ? `${fieldName}-error` : undefined,
    };

    switch (field.field_type) {
      case "textarea":
        return (
          <Textarea
            {...commonProps}
            value={value || ""}
            placeholder={field.example_value || ""}
            rows={4}
            className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
          />
        );

      case "number":
        return (
          <Input
            {...commonProps}
            type="number"
            step="any"
            value={value || ""}
            placeholder={field.example_value || ""}
            className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
          />
        );

      case "date":
        return (
          <Input
            {...commonProps}
            type="date"
            value={value || ""}
            className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
          />
        );

      case "email":
        return (
          <Input
            {...commonProps}
            type="email"
            value={value || ""}
            placeholder={field.example_value || "example@domain.com"}
            className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
          />
        );

      case "signature":
        return (
          <div className="space-y-2">
            <Input
              {...commonProps}
              type="text"
              value={value || ""}
              placeholder="Enter signature text or draw..."
              className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
            />
            <p className="text-xs text-slate-500">Signature drawing coming in V1.6</p>
          </div>
        );

      default:
        return (
          <Input
            {...commonProps}
            type="text"
            value={value || ""}
            placeholder={field.example_value || ""}
            className={fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}
          />
        );
    }
  };

  return (
    <div className="space-y-2">
      {field.field_type === "list" ? (
        <ListField field={field} />
      ) : (
        <Controller
          name={fieldName}
          control={control}
          defaultValue={getDefaultValue()}
          render={renderInput}
        />
      )}

      {(field.description || field.example_value || field.validation_rule) && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <Badge variant="outline" className="gap-1 bg-slate-50 border-slate-200">
            {icon}
            <span>{typeLabel}</span>
          </Badge>
          {field.is_required && (
            <Badge variant="default" className="bg-red-50 text-red-700 border-red-200">
              Required
            </Badge>
          )}
          {field.validation_rule && (
            <Badge variant="outline" className="bg-amber-50 border-amber-200 text-amber-700">
              Validation: {field.validation_rule}
            </Badge>
          )}
          {field.section && (
            <Badge variant="outline" className="bg-blue-50 border-blue-200 text-blue-700">
              Section: {field.section}
            </Badge>
          )}
          {field.description && (
            <span className="ml-auto">{field.description}</span>
          )}
        </div>
      )}
      {fieldError && (
        <p id={`${fieldName}-error`} className="text-sm text-red-600" role="alert">
          {typeof fieldError === "string" ? fieldError : fieldError.message}
        </p>
      )}
    </div>
  );
}