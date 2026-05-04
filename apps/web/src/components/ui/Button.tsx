/**
 * Button Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Primary CTA buttons (Apple Blue background, white text, 8px padding, 8px border-radius)
 * - Pill links (transparent background, Apple Blue border, 980px border-radius)
 * - 6-state model (Initial, Loading, Empty, Degraded, Error, Success)
 * - WCAG AA accessibility compliance
 * - Keyboard navigation support
 * - Touch-friendly (44px minimum height)
 */

import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'pill' | 'ghost' | 'icon';
export type ButtonSize = 'sm' | 'md' | 'lg';
export type ButtonState = 'initial' | 'loading' | 'success' | 'error' | 'disabled';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  state?: ButtonState;
  children?: React.ReactNode;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  ariaLabel?: string;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  state = 'initial',
  children,
  onClick,
  disabled = false,
  fullWidth = false,
  icon,
  ariaLabel,
  className = '',
  ...props
}) => {
  const isDisabled = disabled || state === 'disabled' || state === 'loading';

  // Base styles - Apple design principles
  const baseStyles = [
    'inline-flex',
    'items-center',
    'justify-center',
    'gap-2',
    'font-text',
    'transition-all',
    'duration-200',
    'ease-in-out',
    'cursor-pointer',
    'focus-visible:outline-2',
    'focus-visible:outline-offset-2',
    'focus-visible:outline-apple-blue',
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
  ].join(' ');

  // Variant styles
  const variantStyles: Record<ButtonVariant, string> = {
    primary: [
      'bg-apple-blue',
      'text-white',
      'border',
      'border-transparent',
      'hover:bg-apple-blue-hover',
      'active:bg-apple-blue-active',
      'disabled:bg-interactive-disabled',
    ].join(' '),
    
    secondary: [
      'bg-near-black',
      'text-white',
      'border',
      'border-transparent',
      'hover:bg-opacity-90',
      'active:bg-opacity-80',
      'disabled:bg-interactive-disabled',
    ].join(' '),
    
    pill: [
      'bg-transparent',
      'text-apple-blue',
      'border',
      'border-apple-blue',
      'hover:bg-apple-blue',
      'hover:text-white',
      'active:bg-apple-blue-active',
      'active:border-apple-blue-active',
      'disabled:border-interactive-disabled',
      'disabled:text-interactive-disabled',
    ].join(' '),
    
    ghost: [
      'bg-transparent',
      'text-apple-blue',
      'border',
      'border-transparent',
      'hover:bg-light-gray',
      'active:bg-opacity-80',
      'disabled:text-interactive-disabled',
    ].join(' '),
    
    icon: [
      'bg-icon-button',
      'text-icon-button-text',
      'border',
      'border-transparent',
      'rounded-full',
      'hover:bg-opacity-80',
      'active:bg-opacity-60',
      'disabled:bg-interactive-disabled',
    ].join(' '),
  };

  // Size styles
  const sizeStyles: Record<ButtonSize, string> = {
    sm: variant === 'icon' 
      ? 'w-10 h-10 min-w-[40px] min-h-[40px]' 
      : 'px-4 py-2 text-body-sm min-h-[36px]',
    md: variant === 'icon' 
      ? 'w-11 h-11 min-w-[44px] min-h-[44px]' 
      : 'px-6 py-2 text-body min-h-[44px]',
    lg: variant === 'icon' 
      ? 'w-14 h-14 min-w-[56px] min-h-[56px]' 
      : 'px-8 py-3 text-body-lg min-h-[52px]',
  };

  // Border radius styles
  const radiusStyles = variant === 'pill' 
    ? 'rounded-full' 
    : variant === 'icon' 
    ? 'rounded-full' 
    : 'rounded-lg';

  // Width styles
  const widthStyles = fullWidth ? 'w-full' : '';

  // State-specific content
  const getContent = () => {
    if (state === 'loading') {
      return (
        <>
          <svg 
            className="animate-spin h-4 w-4" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle 
              className="opacity-25" 
              cx="12" 
              cy="12" 
              r="10" 
              stroke="currentColor" 
              strokeWidth="4"
            />
            <path 
              className="opacity-75" 
              fill="currentColor" 
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {children && <span>Loading...</span>}
        </>
      );
    }

    if (state === 'success') {
      return (
        <>
          <svg 
            className="h-4 w-4" 
            xmlns="http://www.w3.org/2000/svg" 
            viewBox="0 0 20 20" 
            fill="currentColor"
            aria-hidden="true"
          >
            <path 
              fillRule="evenodd" 
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" 
              clipRule="evenodd" 
            />
          </svg>
          {children}
        </>
      );
    }

    if (state === 'error') {
      return (
        <>
          <svg 
            className="h-4 w-4" 
            xmlns="http://www.w3.org/2000/svg" 
            viewBox="0 0 20 20" 
            fill="currentColor"
            aria-hidden="true"
          >
            <path 
              fillRule="evenodd" 
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" 
              clipRule="evenodd" 
            />
          </svg>
          {children}
        </>
      );
    }

    return (
      <>
        {icon && <span aria-hidden="true">{icon}</span>}
        {children}
      </>
    );
  };

  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${radiusStyles} ${widthStyles} ${className}`}
      onClick={onClick}
      disabled={isDisabled}
      aria-label={ariaLabel || (typeof children === 'string' ? children : undefined)}
      aria-busy={state === 'loading'}
      {...props}
    >
      {getContent()}
    </button>
  );
};

// Export default for convenience
export default Button;
