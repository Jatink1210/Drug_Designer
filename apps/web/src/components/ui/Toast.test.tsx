/**
 * Unit tests for Toast component
 * 
 * Tests toast notification functionality including:
 * - Rendering and display
 * - Variants and positions
 * - Auto dismiss
 * - Actions and close button
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Toast, ToastContainer, useToast } from './Toast';

describe('Toast Component', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render toast with message', () => {
      render(<Toast message="Test toast message" />);
      expect(screen.getByText('Test toast message')).toBeInTheDocument();
    });

    it('should render toast with title and description', () => {
      render(
        <Toast title="Success" description="Operation completed successfully" />
      );
      
      expect(screen.getByText('Success')).toBeInTheDocument();
      expect(screen.getByText('Operation completed successfully')).toBeInTheDocument();
    });

    it('should render toast without title', () => {
      render(<Toast description="Just a description" />);
      
      expect(screen.getByText('Just a description')).toBeInTheDocument();
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    });
  });

  describe('Variants', () => {
    it('should render success toast', () => {
      const { container } = render(<Toast message="Success" variant="success" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('variant-success');
    });

    it('should render error toast', () => {
      const { container } = render(<Toast message="Error" variant="error" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('variant-error');
    });

    it('should render warning toast', () => {
      const { container } = render(<Toast message="Warning" variant="warning" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('variant-warning');
    });

    it('should render info toast', () => {
      const { container } = render(<Toast message="Info" variant="info" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('variant-info');
    });

    it('should use info variant by default', () => {
      const { container } = render(<Toast message="Default" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('variant-info');
    });
  });

  describe('Positions', () => {
    it('should render toast at top-right position', () => {
      render(<ToastContainer position="top-right" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-top-right');
    });

    it('should render toast at top-left position', () => {
      render(<ToastContainer position="top-left" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-top-left');
    });

    it('should render toast at bottom-right position', () => {
      render(<ToastContainer position="bottom-right" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-bottom-right');
    });

    it('should render toast at bottom-left position', () => {
      render(<ToastContainer position="bottom-left" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-bottom-left');
    });

    it('should render toast at top-center position', () => {
      render(<ToastContainer position="top-center" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-top-center');
    });

    it('should render toast at bottom-center position', () => {
      render(<ToastContainer position="bottom-center" />);
      const container = screen.getByTestId('toast-container');
      expect(container).toHaveClass('position-bottom-center');
    });
  });

  describe('Icons', () => {
    it('should render default icon for success variant', () => {
      render(<Toast message="Success" variant="success" />);
      const icon = screen.getByTestId('toast-icon');
      expect(icon).toHaveClass('icon-success');
    });

    it('should render default icon for error variant', () => {
      render(<Toast message="Error" variant="error" />);
      const icon = screen.getByTestId('toast-icon');
      expect(icon).toHaveClass('icon-error');
    });

    it('should render custom icon', () => {
      render(
        <Toast
          message="Custom"
          icon={<span data-testid="custom-icon">🔔</span>}
        />
      );
      
      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
    });

    it('should not render icon when icon prop is null', () => {
      render(<Toast message="No icon" icon={null} />);
      expect(screen.queryByTestId('toast-icon')).not.toBeInTheDocument();
    });
  });

  describe('Close Functionality', () => {
    it('should render close button when closable', () => {
      render(<Toast message="Closable" closable />);
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });

    it('should call onClose when close button clicked', () => {
      const mockOnClose = jest.fn();
      render(<Toast message="Closable" closable onClose={mockOnClose} />);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should remove toast when closed', async () => {
      render(<Toast message="Closable" closable />);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      await waitFor(() => {
        expect(screen.queryByText('Closable')).not.toBeInTheDocument();
      });
    });

    it('should be closable by default', () => {
      render(<Toast message="Default closable" />);
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });
  });

  describe('Auto Dismiss', () => {
    it('should auto dismiss after duration', async () => {
      const mockOnClose = jest.fn();
      render(
        <Toast
          message="Auto dismiss"
          duration={3000}
          onClose={mockOnClose}
        />
      );
      
      expect(screen.getByText('Auto dismiss')).toBeInTheDocument();
      
      act(() => {
        jest.advanceTimersByTime(3000);
      });
      
      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('should not auto dismiss when duration is 0', () => {
      const mockOnClose = jest.fn();
      render(
        <Toast message="No auto dismiss" duration={0} onClose={mockOnClose} />
      );
      
      act(() => {
        jest.advanceTimersByTime(10000);
      });
      
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('should pause auto dismiss on hover', () => {
      const mockOnClose = jest.fn();
      render(
        <Toast message="Hover to pause" duration={3000} onClose={mockOnClose} />
      );
      
      const toast = screen.getByRole('alert');
      
      act(() => {
        jest.advanceTimersByTime(1000);
      });
      
      fireEvent.mouseEnter(toast);
      
      act(() => {
        jest.advanceTimersByTime(3000);
      });
      
      expect(mockOnClose).not.toHaveBeenCalled();
      
      fireEvent.mouseLeave(toast);
      
      act(() => {
        jest.advanceTimersByTime(2000);
      });
      
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Actions', () => {
    it('should render action button', () => {
      render(
        <Toast
          message="With action"
          action={<button>Undo</button>}
        />
      );
      
      expect(screen.getByText('Undo')).toBeInTheDocument();
    });

    it('should handle action button click', () => {
      const mockAction = jest.fn();
      render(
        <Toast
          message="With action"
          action={<button onClick={mockAction}>Retry</button>}
        />
      );
      
      const actionButton = screen.getByText('Retry');
      fireEvent.click(actionButton);
      
      expect(mockAction).toHaveBeenCalledTimes(1);
    });

    it('should render multiple actions', () => {
      render(
        <Toast
          message="Multiple actions"
          action={
            <>
              <button>Action 1</button>
              <button>Action 2</button>
            </>
          }
        />
      );
      
      expect(screen.getByText('Action 1')).toBeInTheDocument();
      expect(screen.getByText('Action 2')).toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    it('should show progress bar when duration is set', () => {
      render(<Toast message="With progress" duration={3000} showProgress />);
      const progressBar = screen.getByTestId('toast-progress');
      expect(progressBar).toBeInTheDocument();
    });

    it('should not show progress bar by default', () => {
      render(<Toast message="No progress" duration={3000} />);
      const progressBar = screen.queryByTestId('toast-progress');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('should animate progress bar', () => {
      render(<Toast message="Animated progress" duration={3000} showProgress />);
      const progressBar = screen.getByTestId('toast-progress');
      expect(progressBar).toHaveClass('animate');
    });
  });

  describe('Accessibility', () => {
    it('should have role="alert"', () => {
      render(<Toast message="Alert" />);
      const toast = screen.getByRole('alert');
      expect(toast).toBeInTheDocument();
    });

    it('should have aria-live="polite" for non-error toasts', () => {
      render(<Toast message="Info" variant="info" />);
      const toast = screen.getByRole('alert');
      expect(toast).toHaveAttribute('aria-live', 'polite');
    });

    it('should have aria-live="assertive" for error toasts', () => {
      render(<Toast message="Error" variant="error" />);
      const toast = screen.getByRole('alert');
      expect(toast).toHaveAttribute('aria-live', 'assertive');
    });

    it('should have accessible close button', () => {
      render(<Toast message="Closable" closable />);
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toHaveAttribute('aria-label');
    });
  });

  describe('Animation', () => {
    it('should animate in when rendered', () => {
      const { container } = render(<Toast message="Animated" />);
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('animate-in');
    });

    it('should animate out when closed', async () => {
      render(<Toast message="Animated close" closable />);
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      const toast = screen.getByRole('alert');
      expect(toast).toHaveClass('animate-out');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <Toast message="Custom" className="custom-toast" />
      );
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveClass('custom-toast');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Toast message="Custom style" style={{ backgroundColor: 'purple' }} />
      );
      const toast = container.querySelector('[role="alert"]');
      expect(toast).toHaveStyle({ backgroundColor: 'purple' });
    });
  });

  describe('Toast Container', () => {
    it('should render toast container', () => {
      render(<ToastContainer />);
      const container = screen.getByTestId('toast-container');
      expect(container).toBeInTheDocument();
    });

    it('should render multiple toasts in container', () => {
      render(
        <ToastContainer>
          <Toast message="Toast 1" />
          <Toast message="Toast 2" />
          <Toast message="Toast 3" />
        </ToastContainer>
      );
      
      expect(screen.getByText('Toast 1')).toBeInTheDocument();
      expect(screen.getByText('Toast 2')).toBeInTheDocument();
      expect(screen.getByText('Toast 3')).toBeInTheDocument();
    });

    it('should limit number of visible toasts', () => {
      render(
        <ToastContainer maxToasts={2}>
          <Toast message="Toast 1" />
          <Toast message="Toast 2" />
          <Toast message="Toast 3" />
        </ToastContainer>
      );
      
      expect(screen.getByText('Toast 1')).toBeInTheDocument();
      expect(screen.getByText('Toast 2')).toBeInTheDocument();
      expect(screen.queryByText('Toast 3')).not.toBeVisible();
    });
  });

  describe('useToast Hook', () => {
    it('should show toast using hook', () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.success('Success message')}>
            Show Toast
          </button>
        );
      };
      
      render(<TestComponent />);
      
      const button = screen.getByText('Show Toast');
      fireEvent.click(button);
      
      expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    it('should show different toast variants using hook', () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <>
            <button onClick={() => toast.success('Success')}>Success</button>
            <button onClick={() => toast.error('Error')}>Error</button>
            <button onClick={() => toast.warning('Warning')}>Warning</button>
            <button onClick={() => toast.info('Info')}>Info</button>
          </>
        );
      };
      
      render(<TestComponent />);
      
      fireEvent.click(screen.getByText('Success'));
      expect(screen.getByText('Success')).toBeInTheDocument();
      
      fireEvent.click(screen.getByText('Error'));
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('should dismiss toast using hook', async () => {
      const TestComponent = () => {
        const toast = useToast();
        const [toastId, setToastId] = React.useState<string | null>(null);
        
        return (
          <>
            <button onClick={() => {
              const id = toast.success('Dismissible');
              setToastId(id);
            }}>
              Show
            </button>
            <button onClick={() => toastId && toast.dismiss(toastId)}>
              Dismiss
            </button>
          </>
        );
      };
      
      render(<TestComponent />);
      
      fireEvent.click(screen.getByText('Show'));
      expect(screen.getByText('Dismissible')).toBeInTheDocument();
      
      fireEvent.click(screen.getByText('Dismiss'));
      
      await waitFor(() => {
        expect(screen.queryByText('Dismissible')).not.toBeInTheDocument();
      });
    });
  });

  describe('Loading Toast', () => {
    it('should show loading toast', () => {
      render(<Toast message="Loading..." isLoading />);
      const spinner = screen.getByTestId('toast-spinner');
      expect(spinner).toBeInTheDocument();
    });

    it('should update loading toast to success', async () => {
      const { rerender } = render(
        <Toast message="Loading..." isLoading />
      );
      
      expect(screen.getByTestId('toast-spinner')).toBeInTheDocument();
      
      rerender(<Toast message="Success!" variant="success" />);
      
      expect(screen.queryByTestId('toast-spinner')).not.toBeInTheDocument();
      expect(screen.getByText('Success!')).toBeInTheDocument();
    });
  });
});
