import { useState, useEffect, useCallback } from "react";
import { useFormContext, Controller, useWatch } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, X } from "lucide-react";

interface ListFieldProps {
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

function parseJSONArray(value: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function ListField({ field }: ListFieldProps) {
  const { control, setValue, formState: { errors } } = useFormContext();
  const fieldName = field.field_name;
  const fieldError = errors[fieldName] as { message?: string } | undefined;

  // Internal state for the list items
  const [items, setItems] = useState<string[]>(() => parseJSONArray(field.default_value));
  const [touched, setTouched] = useState(false);

  // Watch the form value to sync external changes (reset, etc.)
  const formValue = useWatch({ control, name: fieldName });
  useEffect(() => {
    if (Array.isArray(formValue)) {
      if (JSON.stringify(formValue) !== JSON.stringify(items)) {
        setItems(formValue);
      }
    }
  }, [formValue]); // Remove items from deps

  // Sync internal state to form (as array)
  useEffect(() => {
    setValue(fieldName, items, { shouldValidate: touched, shouldDirty: touched });
  }, [items, fieldName, setValue, touched]);

  const handleBlur = useCallback(() => {
    setTouched(true);
  }, []);

  const handleUpdate = useCallback((index: number, newValue: string) => {
    setItems(prev => {
      const next = [...prev];
      next[index] = newValue;
      return next;
    });
  }, []);

  // Prevent rapid double-clicks
  const [lastClick, setLastClick] = useState(0);
  const handleAddSafe = useCallback(() => {
    const now = Date.now();
    if (now - lastClick < 300) return;
    setLastClick(now);
    setItems(prev => [...prev, ""]);
  }, [lastClick]);

  const handleRemove = useCallback((index: number) => {
    setItems(prev => prev.filter((_, i) => i !== index));
  }, []);

  return (
    <Controller
      name={fieldName}
      control={control}
      render={({ field: controllerField }) => {
        const { onBlur: controllerBlur } = controllerField;

        return (
          <div className="space-y-2">
            {items.map((item, index) => (
              <div key={`${fieldName}-${index}`} className="flex items-center gap-2">
                <Input
                  value={item}
                  onChange={(e) => handleUpdate(index, e.target.value)}
                  onBlur={() => { handleBlur(); controllerBlur(); }}
                  placeholder={field.example_value || `Item ${index + 1}`}
                  className={`flex-1 ${fieldError ? "border-red-500 focus:border-red-500 focus:ring-red-500" : ""}`}
                />
                {items.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemove(index)}
                    className="text-red-500 hover:text-red-700"
                    aria-label={`Remove item ${index + 1}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddSafe}
              className="w-full"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Item
            </Button>
            {fieldError && (
              <p className="text-sm text-red-600" role="alert">
                {typeof fieldError === "string" ? fieldError : fieldError.message}
              </p>
            )}
          </div>
        );
      }}
    />
  );
}