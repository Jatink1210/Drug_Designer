/**
 * Unit tests for Badge component
 * 
 * Tests badge functionality including:
 * - Rendering and display
 * - Variants and colors
 * - Sizes
 * - Icons and close button
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Badge } from './Badge';

describe('Badge Component', () => {
  describe('Rendering', () => {
    it('should render badge with text', () => {
      render(<Badge>New</Badge>);
      expect(screen.getByText('New')).toBeInTheDocument();
    });

    it('should render badge with number', () => {
      render(<Badge>42</Badge>);
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('should render empty badge', () => {
      const { container } = render(<Badge />);
      const badge = container.firstChild;
      expect(badge).toBeInTheDocument();
      expect(badge).toBeEmptyDOMElement();
    });
  });

  describe('Variants', () => {
    it('should render solid variant', () => {
      render(<Badge variant="solid">Solid</Badge>);
      const badge = screen.getByText('Solid');
      expect(badge).toHaveClass('variant-solid');
    });

    it('should render subtle variant', () => {
      render(<Badge variant="subtle">Subtle</Badge>);
      const badge = screen.getByText('Subtle');
      expect(badge).toHaveClass('variant-subtle');
    });

    it('should render outline variant', () => {
      render(<Badge variant="outline">Outline</Badge>);
      const badge = screen.getByText('Outline');
      expect(badge).toHaveClass('variant-outline');
    });

    it('should use solid variant by default', () => {
      render(<Badge>Default</Badge>);
      const badge = screen.getByText('Default');
      expect(badge).toHaveClass('variant-solid');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      render(<Badge colorScheme="primary">Primary</Badge>);
      const badge = screen.getByText('Primary');
      expect(badge).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      render(<Badge colorScheme="success">Success</Badge>);
      const badge = screen.getByText('Success');
      expect(badge).toHaveClass('color-success');
    });

    it('should render with warning color', () => {
      render(<Badge colorScheme="warning">Warning</Badge>);
      const badge = screen.getByText('Warning');
      expect(badge).toHaveClass('color-warning');
    });

    it('should render with error color', () => {
      render(<Badge colorScheme="error">Error</Badge>);
      const badge = screen.getByText('Error');
      expect(badge).toHaveClass('color-error');
    });

    it('should render with info color', () => {
      render(<Badge colorScheme="info">Info</Badge>);
      const badge = screen.getByText('Info');
      expect(badge).toHaveClass('color-info');
    });

    it('should render with gray color', () => {
      render(<Badge colorScheme="gray">Gray</Badge>);
      const badge = screen.getByText('Gray');
      expect(badge).toHaveClass('color-gray');
    });
  });

  describe('Sizes', () => {
    it('should render small badge', () => {
      render(<Badge size="sm">Small</Badge>);
      const badge = screen.getByText('Small');
      expect(badge).toHaveClass('size-sm');
    });

    it('should render medium badge', () => {
      render(<Badge size="md">Medium</Badge>);
      const badge = screen.getByText('Medium');
      expect(badge).toHaveClass('size-md');
    });

    it('should render large badge', () => {
      render(<Badge size="lg">Large</Badge>);
      const badge = screen.getByText('Large');
      expect(badge).toHaveClass('size-lg');
    });

    it('should use medium size by default', () => {
      render(<Badge>Default</Badge>);
      const badge = screen.getByText('Default');
      expect(badge).toHaveClass('size-md');
    });
  });

  describe('Icons', () => {
    it('should render badge with left icon', () => {
      render(
        <Badge leftIcon={<span data-testid="left-icon">🔵</span>}>
          With Icon
        </Badge>
      );
      
      expect(screen.getByTestId('left-icon')).toBeInTheDocument();
      expect(screen.getByText('With Icon')).toBeInTheDocument();
    });

    it('should render badge with right icon', () => {
      render(
        <Badge rightIcon={<span data-testid="right-icon">→</span>}>
          With Icon
        </Badge>
      );
      
      expect(screen.getByTestId('right-icon')).toBeInTheDocument();
      expect(screen.getByText('With Icon')).toBeInTheDocument();
    });

    it('should render badge with both icons', () => {
      render(
        <Badge
          leftIcon={<span data-testid="left-icon">←</span>}
          rightIcon={<span data-testid="right-icon">→</span>}
        >
          Both Icons
        </Badge>
      );
      
      expect(screen.getByTestId('left-icon')).toBeInTheDocument();
      expect(screen.getByTestId('right-icon')).toBeInTheDocument();
    });
  });

  describe('Close Button', () => {
    it('should render close button when closable', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Badge closable onClose={mockOnClose}>
          Closable
        </Badge>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });

    it('should call onClose when close button clicked', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Badge closable onClose={mockOnClose}>
          Closable
        </Badge>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should not render close button when not closable', () => {
      render(<Badge>Not Closable</Badge>);
      
      const closeButton = screen.queryByRole('button', { name: /close/i });
      expect(closeButton).not.toBeInTheDocument();
    });
  });

  describe('Dot Indicator', () => {
    it('should render with dot indicator', () => {
      render(<Badge withDot>With Dot</Badge>);
      
      const dot = screen.getByTestId('badge-dot');
      expect(dot).toBeInTheDocument();
    });

    it('should not render dot by default', () => {
      render(<Badge>No Dot</Badge>);
      
      const dot = screen.queryByTestId('badge-dot');
      expect(dot).not.toBeInTheDocument();
    });
  });

  describe('Pill Shape', () => {
    it('should render as pill when pill prop is true', () => {
      render(<Badge pill>Pill Badge</Badge>);
      
      const badge = screen.getByText('Pill Badge');
      expect(badge).toHaveClass('pill');
    });

    it('should render with default border radius when pill is false', () => {
      render(<Badge>Regular Badge</Badge>);
      
      const badge = screen.getByText('Regular Badge');
      expect(badge).not.toHaveClass('pill');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      render(<Badge className="custom-badge">Custom</Badge>);
      
      const badge = screen.getByText('Custom');
      expect(badge).toHaveClass('custom-badge');
    });

    it('should apply custom styles', () => {
      render(
        <Badge style={{ backgroundColor: 'purple' }}>
          Custom Style
        </Badge>
      );
      
      const badge = screen.getByText('Custom Style');
      expect(badge).toHaveStyle({ backgroundColor: 'purple' });
    });
  });

  describe('Accessibility', () => {
    it('should have proper role', () => {
      render(<Badge>Status</Badge>);
      
      const badge = screen.getByText('Status');
      expect(badge).toHaveAttribute('role', 'status');
    });

    it('should support aria-label', () => {
      render(<Badge aria-label="Notification count">5</Badge>);
      
      const badge = screen.getByLabelText('Notification count');
      expect(badge).toBeInTheDocument();
    });

    it('should have accessible close button', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Badge closable onClose={mockOnClose}>
          Closable
        </Badge>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toHaveAttribute('aria-label');
    });
  });

  describe('Numeric Badges', () => {
    it('should render count badge', () => {
      render(<Badge>99+</Badge>);
      expect(screen.getByText('99+')).toBeInTheDocument();
    });

    it('should render zero', () => {
      render(<Badge>0</Badge>);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('should format large numbers', () => {
      render(<Badge max={99}>150</Badge>);
      expect(screen.getByText('99+')).toBeInTheDocument();
    });
  });

  describe('Interactive States', () => {
    it('should be clickable when onClick provided', () => {
      const mockOnClick = jest.fn();
      
      render(<Badge onClick={mockOnClick}>Clickable</Badge>);
      
      const badge = screen.getByText('Clickable');
      fireEvent.click(badge);
      
      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('should show hover state when clickable', () => {
      const mockOnClick = jest.fn();
      
      render(<Badge onClick={mockOnClick}>Hover Me</Badge>);
      
      const badge = screen.getByText('Hover Me');
      expect(badge).toHaveClass('clickable');
    });

    it('should not be clickable by default', () => {
      render(<Badge>Not Clickable</Badge>);
      
      const badge = screen.getByText('Not Clickable');
      expect(badge).not.toHaveClass('clickable');
    });
  });

  describe('Positioning', () => {
    it('should render as absolute positioned badge', () => {
      render(
        <div style={{ position: 'relative' }}>
          <button>Button</button>
          <Badge position="top-right">3</Badge>
        </div>
      );
      
      const badge = screen.getByText('3');
      expect(badge).toHaveClass('position-top-right');
    });

    it('should support different positions', () => {
      const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
      
      positions.forEach((position) => {
        const { rerender } = render(
          <Badge position={position as any}>1</Badge>
        );
        
        const badge = screen.getByText('1');
        expect(badge).toHaveClass(`position-${position}`);
        
        rerender(<></>);
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator', () => {
      render(<Badge isLoading>Loading</Badge>);
      
      const spinner = screen.getByTestId('badge-spinner');
      expect(spinner).toBeInTheDocument();
    });

    it('should hide content when loading', () => {
      render(<Badge isLoading>Hidden</Badge>);
      
      const content = screen.queryByText('Hidden');
      expect(content).not.toBeVisible();
    });
  });

  describe('Truncation', () => {
    it('should truncate long text', () => {
      render(
        <Badge maxWidth={100}>
          This is a very long badge text that should be truncated
        </Badge>
      );
      
      const badge = screen.getByText(/This is a very long/);
      expect(badge).toHaveStyle({ maxWidth: '100px' });
    });
  });
});
