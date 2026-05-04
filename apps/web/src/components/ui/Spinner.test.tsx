/**
 * Unit tests for Spinner component
 * 
 * Tests spinner functionality including:
 * - Rendering and display
 * - Sizes
 * - Colors
 * - Labels and accessibility
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Spinner } from './Spinner';

describe('Spinner Component', () => {
  describe('Rendering', () => {
    it('should render spinner', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Spinner label="Loading..." />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render without label by default', () => {
      render(<Spinner />);
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  describe('Sizes', () => {
    it('should render extra small spinner', () => {
      const { container } = render(<Spinner size="xs" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-xs');
    });

    it('should render small spinner', () => {
      const { container } = render(<Spinner size="sm" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-sm');
    });

    it('should render medium spinner', () => {
      const { container } = render(<Spinner size="md" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-md');
    });

    it('should render large spinner', () => {
      const { container } = render(<Spinner size="lg" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-lg');
    });

    it('should render extra large spinner', () => {
      const { container } = render(<Spinner size="xl" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-xl');
    });

    it('should use medium size by default', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('size-md');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Spinner color="primary" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-primary');
    });

    it('should render with secondary color', () => {
      const { container } = render(<Spinner color="secondary" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-secondary');
    });

    it('should render with success color', () => {
      const { container } = render(<Spinner color="success" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-success');
    });

    it('should render with error color', () => {
      const { container } = render(<Spinner color="error" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-error');
    });

    it('should render with warning color', () => {
      const { container } = render(<Spinner color="warning" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-warning');
    });

    it('should render with white color', () => {
      const { container } = render(<Spinner color="white" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-white');
    });

    it('should use primary color by default', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('color-primary');
    });
  });

  describe('Variants', () => {
    it('should render circular spinner', () => {
      const { container } = render(<Spinner variant="circular" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('variant-circular');
    });

    it('should render dots spinner', () => {
      const { container } = render(<Spinner variant="dots" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('variant-dots');
    });

    it('should render bars spinner', () => {
      const { container } = render(<Spinner variant="bars" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('variant-bars');
    });

    it('should render pulse spinner', () => {
      const { container } = render(<Spinner variant="pulse" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('variant-pulse');
    });

    it('should use circular variant by default', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('variant-circular');
    });
  });

  describe('Speed', () => {
    it('should render with slow speed', () => {
      const { container } = render(<Spinner speed="slow" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('speed-slow');
    });

    it('should render with normal speed', () => {
      const { container } = render(<Spinner speed="normal" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('speed-normal');
    });

    it('should render with fast speed', () => {
      const { container } = render(<Spinner speed="fast" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('speed-fast');
    });

    it('should use normal speed by default', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('speed-normal');
    });
  });

  describe('Thickness', () => {
    it('should render with custom thickness', () => {
      const { container } = render(<Spinner thickness={4} />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveStyle({ borderWidth: '4px' });
    });

    it('should use default thickness', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveStyle({ borderWidth: '2px' });
    });
  });

  describe('Empty Area Color', () => {
    it('should render with custom empty area color', () => {
      const { container } = render(<Spinner emptyColor="gray" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('empty-color-gray');
    });
  });

  describe('Label Position', () => {
    it('should render label below spinner', () => {
      render(<Spinner label="Loading..." labelPosition="bottom" />);
      const container = screen.getByText('Loading...').parentElement;
      expect(container).toHaveClass('label-bottom');
    });

    it('should render label to the right of spinner', () => {
      render(<Spinner label="Loading..." labelPosition="right" />);
      const container = screen.getByText('Loading...').parentElement;
      expect(container).toHaveClass('label-right');
    });

    it('should render label to the left of spinner', () => {
      render(<Spinner label="Loading..." labelPosition="left" />);
      const container = screen.getByText('Loading...').parentElement;
      expect(container).toHaveClass('label-left');
    });

    it('should use bottom position by default', () => {
      render(<Spinner label="Loading..." />);
      const container = screen.getByText('Loading...').parentElement;
      expect(container).toHaveClass('label-bottom');
    });
  });

  describe('Accessibility', () => {
    it('should have role="status"', () => {
      render(<Spinner />);
      const spinner = screen.getByRole('status');
      expect(spinner).toBeInTheDocument();
    });

    it('should have aria-label', () => {
      render(<Spinner aria-label="Loading content" />);
      const spinner = screen.getByLabelText('Loading content');
      expect(spinner).toBeInTheDocument();
    });

    it('should use default aria-label when not provided', () => {
      render(<Spinner />);
      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-label', 'Loading');
    });

    it('should have aria-live="polite"', () => {
      render(<Spinner />);
      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-live', 'polite');
    });

    it('should have aria-busy="true"', () => {
      render(<Spinner />);
      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-busy', 'true');
    });

    it('should use label text as aria-label when provided', () => {
      render(<Spinner label="Processing data" />);
      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-label', 'Processing data');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Spinner className="custom-spinner" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('custom-spinner');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Spinner style={{ margin: '20px' }} />
      );
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Centered Spinner', () => {
    it('should render centered spinner', () => {
      const { container } = render(<Spinner centered />);
      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('centered');
    });

    it('should not be centered by default', () => {
      const { container } = render(<Spinner />);
      const wrapper = container.firstChild;
      expect(wrapper).not.toHaveClass('centered');
    });
  });

  describe('Full Page Spinner', () => {
    it('should render full page spinner', () => {
      const { container } = render(<Spinner fullPage />);
      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('full-page');
    });

    it('should render with overlay when full page', () => {
      const { container } = render(<Spinner fullPage />);
      const overlay = container.querySelector('[data-testid="spinner-overlay"]');
      expect(overlay).toBeInTheDocument();
    });
  });

  describe('Conditional Rendering', () => {
    it('should render when loading is true', () => {
      const { container } = render(<Spinner loading={true} />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toBeInTheDocument();
    });

    it('should not render when loading is false', () => {
      const { container } = render(<Spinner loading={false} />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).not.toBeInTheDocument();
    });

    it('should render by default (loading undefined)', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('With Children', () => {
    it('should render children when not loading', () => {
      render(
        <Spinner loading={false}>
          <div>Content loaded</div>
        </Spinner>
      );
      
      expect(screen.getByText('Content loaded')).toBeInTheDocument();
    });

    it('should render spinner instead of children when loading', () => {
      const { container } = render(
        <Spinner loading={true}>
          <div>Content loaded</div>
        </Spinner>
      );
      
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toBeInTheDocument();
      expect(screen.queryByText('Content loaded')).not.toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should have animation class', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveClass('animate-spin');
    });

    it('should support custom animation duration', () => {
      const { container } = render(<Spinner animationDuration="2s" />);
      const spinner = container.querySelector('[data-testid="spinner"]');
      expect(spinner).toHaveStyle({ animationDuration: '2s' });
    });
  });
});
