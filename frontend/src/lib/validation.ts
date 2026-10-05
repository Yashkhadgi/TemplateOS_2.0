import { z } from "zod";

export interface ValidationRule {
  email?: boolean;
  min?: number;
  max?: number;
}

export function parseValidationRule(rule: string | null): ValidationRule {
  if (!rule) return {};

  const parsed: ValidationRule = {};
  const parts = rule.split("|");

  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed === "email") {
      parsed.email = true;
    } else if (trimmed.startsWith("min:")) {
      const num = parseInt(trimmed.split(":")[1], 10);
      if (!isNaN(num)) parsed.min = num;
    } else if (trimmed.startsWith("max:")) {
      const num = parseInt(trimmed.split(":")[1], 10);
      if (!isNaN(num)) parsed.max = num;
    }
  }

  return parsed;
}

export function getFieldSchema(field: {
  field_type: string;
  is_required: boolean;
  validation_rule: string | null;
}) {
  const rule = parseValidationRule(field.validation_rule);
  let schema: z.ZodType<any> = z.string();

  switch (field.field_type) {
    case "number":
      schema = z.string().refine(
        (val) => val === "" || !isNaN(Number(val)),
        { message: "Must be a valid number" }
      );
      break;
    case "email":
      schema = z.string().email("Must be a valid email address");
      break;
    case "date":
      schema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Must be a valid date (YYYY-MM-DD)");
      break;
    case "textarea":
      schema = z.string();
      break;
    case "list":
      schema = z.array(z.string());
      break;
    case "signature":
      schema = z.string();
      break;
    default:
      schema = z.string();
  }

  if (field.is_required) {
    if (field.field_type === "list") {
      schema = schema.refine((val) => Array.isArray(val) && val.length > 0, {
        message: "This field is required",
      });
    } else {
      schema = schema.refine((val) => val !== "" && val !== undefined, {
        message: "This field is required",
      });
    }
  } else {
    if (field.field_type === "list") {
      schema = schema.optional();
    } else {
      schema = schema.optional().or(z.literal(""));
    }
  }

  if (rule.min !== undefined) {
    if (field.field_type === "number") {
      schema = schema.refine(
        (val) => val === "" || Number(val) >= rule.min!,
        { message: `Must be at least ${rule.min}` }
      );
    } else if (field.field_type === "list") {
      schema = schema.refine(
        (val) => Array.isArray(val) && val.length >= rule.min!,
        { message: `Must have at least ${rule.min} items` }
      );
    } else {
      schema = schema.refine(
        (val) => val === "" || String(val).length >= rule.min!,
        { message: `Must be at least ${rule.min} characters` }
      );
    }
  }

  if (rule.max !== undefined) {
    if (field.field_type === "number") {
      schema = schema.refine(
        (val) => val === "" || Number(val) <= rule.max!,
        { message: `Must be at most ${rule.max}` }
      );
    } else if (field.field_type === "list") {
      schema = schema.refine(
        (val) => Array.isArray(val) && val.length <= rule.max!,
        { message: `Must have at most ${rule.max} items` }
      );
    } else {
      schema = schema.refine(
        (val) => val === "" || String(val).length <= rule.max!,
        { message: `Must be at most ${rule.max} characters` }
      );
    }
  }

  return schema;
}

export function buildFormSchema(fields: Array<{
  field_name: string;
  field_type: string;
  is_required: boolean;
  validation_rule: string | null;
}>) {
  const shape: Record<string, z.ZodType<any>> = {};

  for (const field of fields) {
    shape[field.field_name] = getFieldSchema(field);
  }

  return z.object(shape);
}
