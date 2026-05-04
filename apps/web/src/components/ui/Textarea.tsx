/**
 * Textarea Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Multi-line text input
 * - Apple Blue focus states
 * - Auto-resize option
 * - WCAG AA accessibility compliance
 * - Dark mode support
 */

import React, { useRef, useEffect } from 'react';

export type TextareaSize = 'sm' | 'md' | 'lg';
export type TextareaState = 'default' | 'error' | 'success' | 'disabled';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  size?: TextareaSize;
  state?: TextareaState;
  label?: string;
  helperText?: string;
  errorText?: string;
  successText?: string;
  fullWidth?: boolean;
  autoResize?: boolean;
  minRows?: number;
  maxRows?: number;
}

export const Textarea: React.FC<TextareaProps> = ({
  size = 'md',
  state = 'default',
  label,
  helperText,
  errorText,
  successText,
  fullWidth = false,
  autoResize = false,
  minRows = 3,
  maxRows = 10,
  className = '',
  id,
  disabled = false,
  value,
  onChange,
  ...props
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`;
  const isDisabled = disabled || state === 'disabled';
  const isError = state === 'error';
  const isSuccess = state === 'success';

  // Auto-resize functionality
  useEffect(() => {
    if (autoResize && textareaRef.current) {
      const textarea = textareaRef.current;
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      const lineHeight = parseInt(getComputedStyle(textarea).lineHeight);
      const minHeight = lineHeight * minRows;
      const maxHeight = lineHeight * maxRows;
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;
    }
  }, [value, autoResize, minRows, maxRows]);

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
    'resize-none',
  ].join(' ');

  // Size styles
  const sizeStyles: Record<TextareaSize, string> = {
    sm: 'px-3 py-2 text-body-sm',
    md: 'px-4 py-3 text-body',
    lg: 'px-5 py-4 text-body-lg',
  };

  // State styles
  const stateStyles: Record<TextareaState, string> = {
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

  const displayText = isError && errorText ? errorText : isSuccess && successText ? successText : helperText;
  const displayTextColor = isError ? 'text-error dark:text-error-dark' : isSuccess ? 'text-success dark:text-success-dark' : 'text-text-secondary dark:text-text-secondary-dark';

  return (
    <div className={`${fullWidth ? 'w-full' : ''}`}>
      {label && (
        <label
          htmlFor={textareaId}
          className="block mb-2 text-body-sm font-medium text-text-primary dark:text-text-primary-dark"
        >
          {label}
        </label>
      )}
      
      <textarea
        ref={textareaRef}
        id={textareaId}
        className={`${baseStyles} ${sizeStyles[size]} ${stateStyles[state]} ${widthStyles} ${className}`}
        disabled={isDisabled}
        aria-invalid={isError}
        aria-describedby={displayText ? `${textareaId}-helper` : undefined}
        rows={autoResize ? minRows : props.rows || minRows}
        value={value}
        onChange={onChange}
        {...props}
      />
      
      {displayText && (
        <p
          id={`${textareaId}-helper`}
          className={`mt-2 text-body-sm ${displayTextColor}`}
          role={isError ? 'alert' : undefined}
        >
          {displayText}
        </p>
      )}
    </div>
  );
};

export default Textarea;
