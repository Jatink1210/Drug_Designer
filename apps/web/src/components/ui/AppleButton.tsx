/**
 * Apple-Style Button Component
 * 
 * TODO: Task 7.3 - Implement Apple-style component library
 * TODO: Primary CTA buttons (Apple Blue background, white text, 8px padding, 8px border-radius)
 * TODO: Pill links (transparent background, Apple Blue border, 980px border-radius)
 * TODO: 6-state model (Initial, Loading, Empty, Degraded, Error, Success)
 * TODO: Add hover/active/disabled states
 * TODO: Add accessibility support (ARIA labels, keyboard navigation)
 */

import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'pill' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';
export type ButtonState = 'initial' | 'loading' | 'success' | 'error' | 'disabled';

export interface AppleButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  state?: ButtonState;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  className?: string;
}

export const AppleButton: React.FC<AppleButtonProps> = ({
  variant = 'primary',
  size = 'md',
  state = 'initial',
  children,
  onClick,
  disabled = false,
  fullWidth = false,
  icon,
  className = ''
}) => {
  // TODO: Implement button styling based on variant
  // TODO: Implement size variations
  // TODO: Implement state-based styling
  // TODO: Add loading spinner for loading state
  // TODO: Add success/error icons
  // TODO: Add smooth transitions
  
  const baseStyles = 'font-semibold transition-all duration-200 ease-in-out';
  
  // TODO: Implement variant styles
  const variantStyles = {
    primary: 'bg-apple-blue text-white hover:bg-apple-blue-hover active:bg-apple-blue-active',
    secondary: 'bg-light-gray text-primary hover:bg-gray-200',
    pill: 'bg-transparent border-2 border-apple-blue text-apple-blue hover:bg-apple-blue hover:text-white',
    ghost: 'bg-transparent text-apple-blue hover:bg-light-gray'
  };
  
  // TODO: Implement size styles
  const sizeStyles = {
    sm: 'px-4 py-2 text-body-sm rounded-md',
    md: 'px-6 py-3 text-body rounded-lg',
    lg: 'px-8 py-4 text-body-lg rounded-xl'
  };
  
  // TODO: Implement state styles
  const stateStyles = {
    initial: '',
    loading: 'opacity-75 cursor-wait',
    success: 'bg-success text-white',
    error: 'bg-error text-white',
    disabled: 'opacity-50 cursor-not-allowed'
  };
  
  const pillStyles = variant === 'pill' ? 'rounded-full' : '';
  const widthStyles = fullWidth ? 'w-full' : '';
  
  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${stateStyles[state]} ${pillStyles} ${widthStyles} ${className}`}
      onClick={onClick}
      disabled={disabled || state === 'disabled' || state === 'loading'}
    >
      {icon && <span className="mr-2">{icon}</span>}
      {state === 'loading' ? 'Loading...' : children}
    </button>
  );
};

// TODO: Add ButtonGroup component for grouped buttons
// TODO: Add IconButton component for icon-only buttons
// TODO: Add LinkButton component for link-styled buttons
