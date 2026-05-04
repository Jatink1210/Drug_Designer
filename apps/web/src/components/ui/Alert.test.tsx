/**
 * Unit tests for Alert component
 * 
 * Tests alert functionality including:
 * - Rendering and display
 * - Variants (success, error, warning, info)
 * - Close functionality
 * - Icons and actions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Alert } from './Alert';

describe('Alert Component', () => {
  describe('Rendering', () => {
    it('should render alert with message', () => {
      render(<Alert>This is an alert message</Alert>);
      expect(screen.getByText('This is an alert message')).toBeInTheDocument();
    });

    it('should render alert with title and description', () => {
      render(
        <Alert title="Alert Title">
          Alert description text
        </Alert>
      );
      
      expect(screen.getByText('Alert Title')).toBeInTheDocument();
      expect(screen.getByText('Alert description text')).toBeInTheDocument();
    });

    it('should render alert without title', () => {
      render(<Alert>Just description</Alert>);
      
      expect(screen.getByText('Just description')).toBeInTheDocument();
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    });
  });

  describe('Variants', () => {
    it('should render success alert', () => {
      render(<Alert variant="success">Success message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('variant-success');
    });

    it('should render error alert', () => {
      render(<Alert variant="error">Error message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('variant-error');
    });

    it('should render warning alert', () => {
      render(<Alert variant="warning">Warning message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('variant-warning');
    });

    it('should render info alert', () => {
      render(<Alert variant="info">Info message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('variant-info');
    });

    it('should use info variant by default', () => {
      render(<Alert>Default message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('variant-info');
    });
  });

  describe('Icons', () => {
    it('should render default icon for success variant', () => {
      render(<Alert variant="success">Success</Alert>);
      
      const icon = screen.getByTestId('alert-icon');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('icon-success');
    });

    it('should render default icon for error variant', () => {
      render(<Alert variant="error">Error</Alert>);
      
      const icon = screen.getByTestId('alert-icon');
      expect(icon).toHaveClass('icon-error');
    });

    it('should render custom icon', () => {
      render(
        <Alert icon={<span data-testid="custom-icon">🔔</span>}>
          Custom icon alert
        </Alert>
      );
      
      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
      expect(screen.queryByTestId('alert-icon')).not.toBeInTheDocument();
    });

    it('should not render icon when icon prop is null', () => {
      render(<Alert icon={null}>No icon</Alert>);
      
      expect(screen.queryByTestId('alert-icon')).not.toBeInTheDocument();
    });
  });

  describe('Close Functionality', () => {
    it('should render close button when closable', () => {
      render(<Alert closable>Closable alert</Alert>);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });

    it('should call onClose when close button clicked', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Alert closable onClose={mockOnClose}>
          Closable alert
        </Alert>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should remove alert from DOM when closed', async () => {
      render(<Alert closable>Closable alert</Alert>);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      await waitFor(() => {
        expect(screen.queryByText('Closable alert')).not.toBeInTheDocument();
      });
    });

    it('should not render close button by default', () => {
      render(<Alert>Not closable</Alert>);
      
      const closeButton = screen.queryByRole('button', { name: /close/i });
      expect(closeButton).not.toBeInTheDocument();
    });
  });

  describe('Actions', () => {
    it('should render action buttons', () => {
      render(
        <Alert
          actions={
            <>
              <button>Action 1</button>
              <button>Action 2</button>
            </>
          }
        >
          Alert with actions
        </Alert>
      );
      
      expect(screen.getByText('Action 1')).toBeInTheDocument();
      expect(screen.getByText('Action 2')).toBeInTheDocument();
    });

    it('should handle action button clicks', () => {
      const mockAction = jest.fn();
      
      render(
        <Alert
          actions={<button onClick={mockAction}>Click Me</button>}
        >
          Alert with action
        </Alert>
      );
      
      const actionButton = screen.getByText('Click Me');
      fireEvent.click(actionButton);
      
      expect(mockAction).toHaveBeenCalledTimes(1);
    });
  });

  describe('Styling', () => {
    it('should apply custom className', () => {
      render(<Alert className="custom-alert">Custom</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('custom-alert');
    });

    it('should apply custom styles', () => {
      render(
        <Alert style={{ backgroundColor: 'purple' }}>
          Custom style
        </Alert>
      );
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveStyle({ backgroundColor: 'purple' });
    });

    it('should render with solid style', () => {
      render(<Alert styleType="solid">Solid alert</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('style-solid');
    });

    it('should render with subtle style', () => {
      render(<Alert styleType="subtle">Subtle alert</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('style-subtle');
    });

    it('should render with left accent', () => {
      render(<Alert styleType="left-accent">Left accent</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('style-left-accent');
    });

    it('should render with top accent', () => {
      render(<Alert styleType="top-accent">Top accent</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('style-top-accent');
    });
  });

  describe('Accessibility', () => {
    it('should have role="alert"', () => {
      render(<Alert>Alert message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });

    it('should have aria-live="polite" for non-error alerts', () => {
      render(<Alert variant="info">Info message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });

    it('should have aria-live="assertive" for error alerts', () => {
      render(<Alert variant="error">Error message</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'assertive');
    });

    it('should have accessible close button', () => {
      render(<Alert closable>Closable</Alert>);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toHaveAttribute('aria-label');
    });

    it('should support custom aria-label', () => {
      render(<Alert aria-label="Custom alert">Message</Alert>);
      
      const alert = screen.getByLabelText('Custom alert');
      expect(alert).toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should animate in when rendered', () => {
      render(<Alert animated>Animated alert</Alert>);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('animate-in');
    });

    it('should animate out when closed', async () => {
      render(<Alert closable animated>Animated closable</Alert>);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('animate-out');
    });
  });

  describe('Auto Dismiss', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should auto dismiss after duration', async () => {
      const mockOnClose = jest.fn();
      
      render(
        <Alert autoDismiss duration={3000} onClose={mockOnClose}>
          Auto dismiss alert
        </Alert>
      );
      
      expect(screen.getByText('Auto dismiss alert')).toBeInTheDocument();
      
      jest.advanceTimersByTime(3000);
      
      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('should not auto dismiss when autoDismiss is false', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Alert autoDismiss={false} onClose={mockOnClose}>
          No auto dismiss
        </Alert>
      );
      
      jest.advanceTimersByTime(5000);
      
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('should pause auto dismiss on hover', () => {
      const mockOnClose = jest.fn();
      
      render(
        <Alert autoDismiss duration={3000} onClose={mockOnClose}>
          Hover to pause
        </Alert>
      );
      
      const alert = screen.getByRole('alert');
      
      jest.advanceTimersByTime(1000);
      fireEvent.mouseEnter(alert);
      jest.advanceTimersByTime(3000);
      
      expect(mockOnClose).not.toHaveBeenCalled();
      
      fireEvent.mouseLeave(alert);
      jest.advanceTimersByTime(2000);
      
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Progress Bar', () => {
    it('should show progress bar when autoDismiss is enabled', () => {
      render(
        <Alert autoDismiss duration={3000} showProgress>
          With progress
        </Alert>
      );
      
      const progressBar = screen.getByTestId('alert-progress');
      expect(progressBar).toBeInTheDocument();
    });

    it('should not show progress bar by default', () => {
      render(<Alert>No progress</Alert>);
      
      const progressBar = screen.queryByTestId('alert-progress');
      expect(progressBar).not.toBeInTheDocument();
    });
  });

  describe('Multiple Alerts', () => {
    it('should render multiple alerts', () => {
      render(
        <>
          <Alert variant="success">Success 1</Alert>
          <Alert variant="error">Error 1</Alert>
          <Alert variant="warning">Warning 1</Alert>
        </>
      );
      
      expect(screen.getByText('Success 1')).toBeInTheDocument();
      expect(screen.getByText('Error 1')).toBeInTheDocument();
      expect(screen.getByText('Warning 1')).toBeInTheDocument();
    });
  });

  describe('Links in Alert', () => {
    it('should render links in alert content', () => {
      render(
        <Alert>
          Check out <a href="/docs">our documentation</a> for more info
        </Alert>
      );
      
      const link = screen.getByRole('link', { name: /our documentation/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/docs');
    });
  });
});
