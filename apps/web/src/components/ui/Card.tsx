/**
 * Card Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Evidence cards (light gray background, 8px border-radius, shadow)
 * - 6-state model (Initial, Loading, Empty, Degraded, Error, Success)
 * - WCAG AA accessibility compliance
 * - Responsive design
 * - Dark mode support
 */

import React from 'react';

export type CardVariant = 'default' | 'evidence' | 'elevated' | 'outlined' | 'glass';
export type CardState = 'initial' | 'loading' | 'empty' | 'degraded' | 'error' | 'success';

export interface CardProps {
  variant?: CardVariant;
  state?: CardState;
  children?: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
  interactive?: boolean;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  ariaLabel?: string;
}

export const Card: React.FC<CardProps> = ({
  variant = 'default',
  state = 'initial',
  children,
  className = '',
  padding = 'md',
  onClick,
  interactive = false,
  header,
  footer,
  ariaLabel,
}) => {
  const isInteractive = interactive || !!onClick;

  // Base styles - Apple design principles
  const baseStyles = [
    'rounded-lg',
    'transition-all',
    'duration-200',
    'ease-in-out',
  ].join(' ');

  // Variant styles
  const variantStyles: Record<CardVariant, string> = {
    default: [
      'bg-light-gray',
      'dark:bg-near-black',
    ].join(' '),
    
    evidence: [
      'bg-light-gray',
      'dark:bg-near-black',
      'shadow-sm',
      'hover:shadow-md',
    ].join(' '),
    
    elevated: [
      'bg-white',
      'dark:bg-near-black',
      'shadow-md',
      'hover:shadow-lg',
    ].join(' '),
    
    outlined: [
      'bg-transparent',
      'border',
      'border-divider',
      'dark:border-divider-dark',
    ].join(' '),
    
    glass: [
      'bg-glass-light',
      'dark:bg-glass-dark',
      'backdrop-blur-md',
      'border',
      'border-glass-border',
      'dark:border-glass-border-dark',
    ].join(' '),
  };

  // Interactive styles
  const interactiveStyles = isInteractive ? [
    'cursor-pointer',
    'hover:scale-[1.01]',
    'active:scale-[0.99]',
    'focus-visible:outline-2',
    'focus-visible:outline-offset-2',
    'focus-visible:outline-apple-blue',
  ].join(' ') : '';

  // Padding styles
  const paddingStyles: Record<typeof padding, string> = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  };

  // State-specific rendering
  const renderContent = () => {
    if (state === 'loading') {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <svg 
            className="animate-spin h-8 w-8 text-apple-blue" 
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
          <p className="text-body text-text-secondary dark:text-text-secondary-dark">
            Loading...
          </p>
        </div>
      );
    }

    if (state === 'empty') {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <svg 
            className="h-12 w-12 text-text-tertiary dark:text-text-tertiary-dark" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
            aria-hidden="true"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={1.5} 
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" 
            />
          </svg>
          <p className="text-body text-text-secondary dark:text-text-secondary-dark">
            No data available
          </p>
        </div>
      );
    }

    if (state === 'degraded') {
      return (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 px-4 py-3 bg-warning-bg dark:bg-warning-bg-dark rounded-lg border border-warning dark:border-warning-dark">
            <svg 
              className="h-5 w-5 text-warning dark:text-warning-dark flex-shrink-0" 
              xmlns="http://www.w3.org/2000/svg" 
              viewBox="0 0 20 20" 
              fill="currentColor"
              aria-hidden="true"
            >
              <path 
                fillRule="evenodd" 
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" 
                clipRule="evenodd" 
              />
            </svg>
            <p className="text-body-sm text-warning dark:text-warning-dark">
              Some features may be unavailable
            </p>
          </div>
          {children}
        </div>
      );
    }

    if (state === 'error') {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <svg 
            className="h-12 w-12 text-error dark:text-error-dark" 
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
          <p className="text-body text-error dark:text-error-dark">
            Failed to load content
          </p>
        </div>
      );
    }

    if (state === 'success') {
      return (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 px-4 py-3 bg-success-bg dark:bg-success-bg-dark rounded-lg border border-success dark:border-success-dark">
            <svg 
              className="h-5 w-5 text-success dark:text-success-dark flex-shrink-0" 
              xmlns="http://www.w3.org/2000/svg" 
              viewBox="0 0 20 20" 
              fill="currentColor"
              aria-hidden="true"
            >
              <path 
                fillRule="evenodd" 
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" 
                clipRule="evenodd" 
              />
            </svg>
            <p className="text-body-sm text-success dark:text-success-dark">
              Operation completed successfully
            </p>
          </div>
          {children}
        </div>
      );
    }

    return children;
  };

  const Component = isInteractive ? 'button' : 'div';

  return (
    <Component
      className={`${baseStyles} ${variantStyles[variant]} ${paddingStyles[padding]} ${interactiveStyles} ${className}`}
      onClick={onClick}
      aria-label={ariaLabel}
      role={isInteractive ? 'button' : undefined}
      tabIndex={isInteractive ? 0 : undefined}
    >
      {header && (
        <div className="mb-4 pb-4 border-b border-divider dark:border-divider-dark">
          {header}
        </div>
      )}
      
      <div className="flex-1">
        {renderContent()}
      </div>
      
      {footer && (
        <div className="mt-4 pt-4 border-t border-divider dark:border-divider-dark">
          {footer}
        </div>
      )}
    </Component>
  );
};

// Export default for convenience
export default Card;
