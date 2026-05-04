/**
 * Select Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Dropdown select input
 * - Apple Blue focus states
 * - WCAG AA accessibility compliance
 * - Dark mode support
 */

import React from 'react';

export type SelectSize = 'sm' | 'md' | 'lg';
export type SelectState = 'default' | 'error' | 'success' | 'disabled';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  size?: SelectSize;
  state?: SelectState;
  label?: string;
  helperText?: string;
  errorText?: string;
  successText?: string;
  options: SelectOption[];
  placeholder?: string;
  fullWidth?: boolean;
}

export const Select: React.FC<SelectProps> = ({
  size = 'md',
  state = 'default',
  label,
  helperText,
  errorText,
  successText,
  options,
  placeholder,
  fullWidth = false,
  className = '',
  id,
  disabled = false,
  ...props
}) => {
  const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;
  const isDisabled = disabled || state === 'disabled';
  const isError = state === 'error';
  const isSuccess = state === 'success';

  // Base styles
  const baseStyles = [
    'font-text',
    'rounded-lg',
    'border',
    'transition-all',
    'duration-200',
    'ease-in-out',
    'focus:outline-none',
    'focus:ring-2',
    'focus:ring-apple-blue',
    'focus:border-apple-blue',
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
    'disabled:bg-light-gray',
    'dark:disabled:bg-near-black',
    'appearance-none',
    'pr-10',
    'cursor-pointer',
  ].join(' ');

  // Size styles
  const sizeStyles: Record<SelectSize, string> = {
    sm: 'px-3 py-2 text-body-sm min-h-[36px]',
    md: 'px-4 py-3 text-body min-h-[44px]',
    lg: 'px-5 py-4 text-body-lg min-h-[52px]',
  };

  // State styles
  const stateStyles: Record<SelectState, string> = {
    default: [
      'bg-white',
      'dark:bg-near-black',
      'border-divider',
      'dark:border-divider-dark',
      'text-text-primary',
      'dark:text-text-primary-dark',
    ].join(' '),
    error: [
      'bg-white',
      'dark:bg-near-black',
      'border-error',
      'dark:border-error-dark',
      'text-text-primary',
      'dark:text-text-primary-dark',
      'focus:ring-error',
      'focus:border-error',
    ].join(' '),
    success: [
      'bg-white',
      'dark:bg-near-black',
      'border-success',
      'dark:border-success-dark',
      'text-text-primary',
      'dark:text-text-primary-dark',
      'focus:ring-success',
      'focus:border-success',
    ].join(' '),
    disabled: [
      'bg-light-gray',
      'dark:bg-near-black',
      'border-divider',
      'dark:border-divider-dark',
      'text-text-tertiary',
      'dark:text-text-tertiary-dark',
    ].join(' '),
  };

  // Width styles
  const widthStyles = fullWidth ? 'w-full' : '';

  const displayText = isError && errorText ? errorText : isSuccess && successText ? successText : helperText;
  const displayTextColor = isError ? 'text-error dark:text-error-dark' : isSuccess ? 'text-success dark:text-success-dark' : 'text-text-secondary dark:text-text-secondary-dark';

  return (
    <div className={`${fullWidth ? 'w-full' : ''}`}>
      {label && (
        <label
          htmlFor={selectId}
          className="block mb-2 text-body-sm font-medium text-text-primary dark:text-text-primary-dark"
        >
          {label}
        </label>
      )}
      
      <div className="relative">
        <select
          id={selectId}
          className={`${baseStyles} ${sizeStyles[size]} ${stateStyles[state]} ${widthStyles} ${className}`}
          disabled={isDisabled}
          aria-invalid={isError}
          aria-describedby={displayText ? `${selectId}-helper` : undefined}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          ))}
        </select>
        
        {/* Chevron icon */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-text-tertiary dark:text-text-tertiary-dark">
          <svg
            className="w-4 h-4"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      </div>
      
      {displayText && (
        <p
          id={`${selectId}-helper`}
          className={`mt-2 text-body-sm ${displayTextColor}`}
          role={isError ? 'alert' : undefined}
        >
          {displayText}
        </p>
      )}
    </div>
  );
};

export default Select;
