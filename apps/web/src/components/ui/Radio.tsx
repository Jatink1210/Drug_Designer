/**
 * Radio Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Custom styled radio button
 * - Apple Blue selected state
 * - WCAG AA accessibility compliance
 * - Keyboard navigation support
 * - Dark mode support
 */

import React from 'react';

export type RadioSize = 'sm' | 'md' | 'lg';

export interface RadioProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size' | 'type'> {
  size?: RadioSize;
  label?: string;
  helperText?: string;
}

export const Radio: React.FC<RadioProps> = ({
  size = 'md',
  label,
  helperText,
  className = '',
  id,
  disabled = false,
  checked,
  ...props
}) => {
  const radioId = id || `radio-${Math.random().toString(36).substr(2, 9)}`;

  // Size styles
  const sizeStyles: Record<RadioSize, { box: string; dot: string; label: string }> = {
    sm: {
      box: 'w-4 h-4',
      dot: 'w-2 h-2',
      label: 'text-body-sm',
    },
    md: {
      box: 'w-5 h-5',
      dot: 'w-2.5 h-2.5',
      label: 'text-body',
    },
    lg: {
      box: 'w-6 h-6',
      dot: 'w-3 h-3',
      label: 'text-body-lg',
    },
  };

  // Base radio styles
  const radioStyles = [
    'rounded-full',
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
    'checked:border-apple-blue',
    'checked:hover:border-apple-blue-hover',
    // Hover state
    'hover:border-apple-blue',
  ].join(' ');

  return (
    <div className={`flex items-start gap-3 ${className}`}>
      <div className="relative flex items-center">
        <input
          type="radio"
          id={radioId}
          className={`${radioStyles} ${sizeStyles[size].box}`}
          disabled={disabled}
          checked={checked}
          aria-describedby={helperText ? `${radioId}-helper` : undefined}
          {...props}
        />
        
        {/* Inner dot */}
        {checked && (
          <div
            className={`absolute pointer-events-none rounded-full bg-apple-blue ${sizeStyles[size].dot}`}
            aria-hidden="true"
          />
        )}
      </div>
      
      {(label || helperText) && (
        <div className="flex-1">
          {label && (
            <label
              htmlFor={radioId}
              className={`block font-medium text-text-primary dark:text-text-primary-dark cursor-pointer ${sizeStyles[size].label} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {label}
            </label>
          )}
          {helperText && (
            <p
              id={`${radioId}-helper`}
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

export default Radio;
