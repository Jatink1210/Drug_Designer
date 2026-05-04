/**
 * Navigation Component - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * Features:
 * - Glass navigation (translucent dark nav with backdrop blur)
 * - Sticky positioning
 * - WCAG AA accessibility compliance
 * - Keyboard navigation support
 * - Responsive design
 * - Dark mode support
 */

import React, { useState, useEffect } from 'react';

export interface NavigationItem {
  label: string;
  href?: string;
  onClick?: () => void;
  icon?: React.ReactNode;
  active?: boolean;
  badge?: string | number;
}

export interface NavigationProps {
  items: NavigationItem[];
  logo?: React.ReactNode;
  actions?: React.ReactNode;
  variant?: 'glass' | 'solid' | 'transparent';
  position?: 'fixed' | 'sticky' | 'static';
  className?: string;
}

export const Navigation: React.FC<NavigationProps> = ({
  items,
  logo,
  actions,
  variant = 'glass',
  position = 'sticky',
  className = '',
}) => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Base styles - Apple design principles
  const baseStyles = [
    'w-full',
    'z-50',
    'transition-all',
    'duration-300',
    'ease-in-out',
  ].join(' ');

  // Position styles
  const positionStyles: Record<typeof position, string> = {
    fixed: 'fixed top-0 left-0 right-0',
    sticky: 'sticky top-0',
    static: 'relative',
  };

  // Variant styles
  const variantStyles: Record<typeof variant, string> = {
    glass: [
      'bg-glass-nav',
      'dark:bg-glass-nav-dark',
      'backdrop-blur-xl',
      'border-b',
      'border-glass-border',
      'dark:border-glass-border-dark',
      scrolled ? 'shadow-lg' : '',
    ].join(' '),
    
    solid: [
      'bg-near-black',
      'dark:bg-pure-black',
      'border-b',
      'border-divider',
      'dark:border-divider-dark',
      scrolled ? 'shadow-md' : '',
    ].join(' '),
    
    transparent: [
      'bg-transparent',
      scrolled ? 'bg-glass-nav dark:bg-glass-nav-dark backdrop-blur-xl' : '',
    ].join(' '),
  };

  return (
    <nav 
      className={`${baseStyles} ${positionStyles[position]} ${variantStyles[variant]} ${className}`}
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="max-w-screen-2xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          {logo && (
            <div className="flex-shrink-0">
              {logo}
            </div>
          )}

          {/* Navigation Items */}
          <div className="hidden md:flex items-center space-x-1">
            {items.map((item, index) => (
              <NavigationLink key={index} item={item} />
            ))}
          </div>

          {/* Actions */}
          {actions && (
            <div className="flex items-center space-x-4">
              {actions}
            </div>
          )}

          {/* Mobile Menu Button */}
          <div className="md:hidden">
            <MobileMenuButton items={items} />
          </div>
        </div>
      </div>
    </nav>
  );
};

// Navigation Link Component
const NavigationLink: React.FC<{ item: NavigationItem }> = ({ item }) => {
  const baseStyles = [
    'inline-flex',
    'items-center',
    'gap-2',
    'px-4',
    'py-2',
    'rounded-lg',
    'font-text',
    'text-body',
    'transition-all',
    'duration-200',
    'ease-in-out',
    'focus-visible:outline-2',
    'focus-visible:outline-offset-2',
    'focus-visible:outline-apple-blue',
  ].join(' ');

  const activeStyles = item.active
    ? 'bg-apple-blue text-white'
    : 'text-text-primary dark:text-text-primary-dark hover:bg-light-gray dark:hover:bg-near-black';

  const Component = item.href ? 'a' : 'button';

  return (
    <Component
      href={item.href}
      onClick={item.onClick}
      className={`${baseStyles} ${activeStyles}`}
      aria-current={item.active ? 'page' : undefined}
    >
      {item.icon && <span aria-hidden="true">{item.icon}</span>}
      <span>{item.label}</span>
      {item.badge && (
        <span 
          className="inline-flex items-center justify-center px-2 py-0.5 text-caption font-semibold rounded-full bg-error dark:bg-error-dark text-white min-w-[20px]"
          aria-label={`${item.badge} notifications`}
        >
          {item.badge}
        </span>
      )}
    </Component>
  );
};

// Mobile Menu Button Component
const MobileMenuButton: React.FC<{ items: NavigationItem[] }> = ({ items }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center p-2 rounded-lg text-text-primary dark:text-text-primary-dark hover:bg-light-gray dark:hover:bg-near-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-apple-blue"
        aria-expanded={isOpen}
        aria-label="Toggle menu"
      >
        {isOpen ? (
          <svg 
            className="h-6 w-6" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
            aria-hidden="true"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M6 18L18 6M6 6l12 12" 
            />
          </svg>
        ) : (
          <svg 
            className="h-6 w-6" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
            aria-hidden="true"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M4 6h16M4 12h16M4 18h16" 
            />
          </svg>
        )}
      </button>

      {/* Mobile Menu */}
      {isOpen && (
        <div className="md:hidden absolute top-16 left-0 right-0 bg-glass-nav dark:bg-glass-nav-dark backdrop-blur-xl border-b border-glass-border dark:border-glass-border-dark shadow-lg">
          <div className="px-4 py-4 space-y-2">
            {items.map((item, index) => (
              <MobileNavigationLink 
                key={index} 
                item={item} 
                onClick={() => setIsOpen(false)} 
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
};

// Mobile Navigation Link Component
const MobileNavigationLink: React.FC<{ 
  item: NavigationItem; 
  onClick: () => void;
}> = ({ item, onClick }) => {
  const baseStyles = [
    'flex',
    'items-center',
    'gap-3',
    'w-full',
    'px-4',
    'py-3',
    'rounded-lg',
    'font-text',
    'text-body',
    'transition-all',
    'duration-200',
    'ease-in-out',
    'focus-visible:outline-2',
    'focus-visible:outline-offset-2',
    'focus-visible:outline-apple-blue',
  ].join(' ');

  const activeStyles = item.active
    ? 'bg-apple-blue text-white'
    : 'text-text-primary dark:text-text-primary-dark hover:bg-light-gray dark:hover:bg-near-black';

  const Component = item.href ? 'a' : 'button';

  const handleClick = () => {
    if (item.onClick) {
      item.onClick();
    }
    onClick();
  };

  return (
    <Component
      href={item.href}
      onClick={handleClick}
      className={`${baseStyles} ${activeStyles}`}
      aria-current={item.active ? 'page' : undefined}
    >
      {item.icon && <span aria-hidden="true">{item.icon}</span>}
      <span className="flex-1 text-left">{item.label}</span>
      {item.badge && (
        <span 
          className="inline-flex items-center justify-center px-2 py-0.5 text-caption font-semibold rounded-full bg-error dark:bg-error-dark text-white min-w-[20px]"
          aria-label={`${item.badge} notifications`}
        >
          {item.badge}
        </span>
      )}
    </Component>
  );
};

// Export default for convenience
export default Navigation;
