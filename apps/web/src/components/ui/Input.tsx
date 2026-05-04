/**
 * Input Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Text inputs, textareas, selects
 * - Apple Blue focus states
 * - WCAG AA accessibility compliance
 * - Error/success states
 * - Dark mode support
 */

import React from 'react';

export type InputVariant = 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' | 'search';
export type InputSize = 'sm' | 'md' | 'lg';
export type InputState = 'default' | 'error' | 'success' | 'disabled';

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  variant?: InputVariant;
  size?: InputSize;
  state?: InputState;
  label?: string;
  helperText?: string;
  errorText?: string;
  successText?: string;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Input: React.FC<InputProps> = ({
  variant = 'text',
  size = 'md',
  state = 'default',
  label,
  helperText,
  errorText,
  successText,
  icon,
  fullWidth = false,
  className = '',
  id,
  disabled = false,
  ...props
}) => {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;
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
  ].join(' ');

  // Size styles
  const sizeStyles: Record<InputSize, string> = {
    sm: 'px-3 py-2 text-body-sm min-h-[36px]',
    md: 'px-4 py-3 text-body min-h-[44px]',
    lg: 'px-5 py-4 text-body-lg min-h-[52px]',
  };

  // State styles
  const stateStyles: Record<InputState, string> = {
    default: [
      'bg-white',
      'dark:bg-near-black',
      'border-divider',
      'dark:border-divider-dark',
      'text-text-primary',
      'dark:text-text-primary-dark',
      'placeholder:text-text-tertiary',
      'dark:placeholder:text-text-tertiary-dark',
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

  // Icon padding adjustment
  const iconPaddingStyles = icon ? 'pl-12' : '';

  const displayText = isError && errorText ? errorText : isSuccess && successText ? successText : helperText;
  const displayTextColor = isError ? 'text-error dark:text-error-dark' : isSuccess ? 'text-success dark:text-success-dark' : 'text-text-secondary dark:text-text-secondary-dark';

  return (
    <div className={`${fullWidth ? 'w-full' : ''}`}>
      {label && (
        <label
          htmlFor={inputId}
          className="block mb-2 text-body-sm font-medium text-text-primary dark:text-text-primary-dark"
        >
          {label}
        </label>
      )}
      
      <div className="relative">
        {icon && (
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-text-tertiary dark:text-text-tertiary-dark pointer-events-none">
            {icon}
          </div>
        )}
        
        <input
          id={inputId}
          type={variant}
          className={`${baseStyles} ${sizeStyles[size]} ${stateStyles[state]} ${widthStyles} ${iconPaddingStyles} ${className}`}
          disabled={isDisabled}
          aria-invalid={isError}
          aria-describedby={displayText ? `${inputId}-helper` : undefined}
          {...props}
        />
      </div>
      
      {displayText && (
        <p
          id={`${inputId}-helper`}
          className={`mt-2 text-body-sm ${displayTextColor}`}
          role={isError ? 'alert' : undefined}
        >
          {displayText}
        </p>
      )}
    </div>
  );
};

export default Input;
