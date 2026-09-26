import { useId, type InputHTMLAttributes } from "react";

export function CheckboxField({ label, ...inputProps }: { label: string } & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const id = useId();
  return (
    <div className="field field-checkbox">
      <input id={id} type="checkbox" {...inputProps} />
      <label htmlFor={id}>{label}</label>
    </div>
  );
}
