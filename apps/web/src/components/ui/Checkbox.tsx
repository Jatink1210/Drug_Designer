/**
 * Checkbox Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Custom styled checkbox
 * - Apple Blue checked state
 * - WCAG AA accessibility compliance
 * - Keyboard navigation support
 * - Dark mode support
 */

import React from 'react';

export type CheckboxSize = 'sm' | 'md' | 'lg';

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size' | 'type'> {
  size?: CheckboxSize;
  label?: string;
  helperText?: string;
  indeterminate?: boolean;
}

export const Checkbox: React.FC<CheckboxProps> = ({
  size = 'md',
  label,
  helperText,
  indeterminate = false,
  className = '',
  id,
  disabled = false,
  checked,
  ...props
}) => {
  const checkboxId = id || `checkbox-${Math.random().toString(36).substr(2, 9)}`;
  const checkboxRef = React.useRef<HTMLInputElement>(null);

  // Set indeterminate state
  React.useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  // Size styles
  const sizeStyles: Record<CheckboxSize, { box: string; label: string }> = {
    sm: {
      box: 'w-4 h-4',
      label: 'text-body-sm',
    },
    md: {
      box: 'w-5 h-5',
      label: 'text-body',
    },
    lg: {
      box: 'w-6 h-6',
      label: 'text-body-lg',
    },
  };

  // Base checkbox styles
  const checkboxStyles = [
    'rounded',
    'border-2',
    'transition-all',
    'duration-200',
    'ease-in-out',
    'cursor-pointer',
    'focus:outline-none',
    'focus:ring-2',
    'focus:ring-apple-blue',
    'focus:ring-offset-2',
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
    'appearance-none',
    'flex',
    'items-center',
    'justify-center',
    // Unchecked state
    'border-divider',
    'dark:border-divider-dark',
    'bg-white',
    'dark:bg-near-black',
    // Checked state
    'checked:bg-apple-blue',
    'checked:border-apple-blue',
    'checked:hover:bg-apple-blue-hover',
    'checked:hover:border-apple-blue-hover',
    // Hover state
    'hover:border-apple-blue',
  ].join(' ');

  return (
    <div className={`flex items-start gap-3 ${className}`}>
      <div className="relative flex items-center">
        <input
          ref={checkboxRef}
          type="checkbox"
          id={checkboxId}
          className={`${checkboxStyles} ${sizeStyles[size].box}`}
          disabled={disabled}
          checked={checked}
          aria-describedby={helperText ? `${checkboxId}-helper` : undefined}
          {...props}
        />
        
        {/* Checkmark icon */}
        {(checked || indeterminate) && (
          <svg
            className={`absolute pointer-events-none text-white ${sizeStyles[size].box}`}
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            {indeterminate ? (
              <path
                fillRule="evenodd"
                d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
                clipRule="evenodd"
              />
            ) : (
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            )}
          </svg>
        )}
      </div>
      
      {(label || helperText) && (
        <div className="flex-1">
          {label && (
            <label
              htmlFor={checkboxId}
              className={`block font-medium text-text-primary dark:text-text-primary-dark cursor-pointer ${sizeStyles[size].label} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {label}
            </label>
          )}
          {helperText && (
            <p
              id={`${checkboxId}-helper`}
              className="mt-1 text-body-sm text-text-secondary dark:text-text-secondary-dark"
            >
              {helperText}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default Checkbox;
