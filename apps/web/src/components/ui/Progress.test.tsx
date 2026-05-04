/**
 * Unit tests for Progress component
 * 
 * Tests progress bar functionality including:
 * - Rendering and display
 * - Value and percentage
 * - Variants and colors
 * - Labels and accessibility
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Progress } from './Progress';

describe('Progress Component', () => {
  describe('Rendering', () => {
    it('should render progress bar', () => {
      const { container } = render(<Progress value={50} />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Progress value={50} label="Loading..." />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render without label by default', () => {
      render(<Progress value={50} />);
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  describe('Value and Percentage', () => {
    it('should display correct percentage', () => {
      render(<Progress value={75} showValue />);
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('should handle 0% value', () => {
      render(<Progress value={0} showValue />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('should handle 100% value', () => {
      render(<Progress value={100} showValue />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('should clamp values above 100', () => {
      const { container } = render(<Progress value={150} />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveStyle({ width: '100%' });
    });

    it('should clamp negative values to 0', () => {
      const { container } = render(<Progress value={-10} />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveStyle({ width: '0%' });
    });

    it('should not show value by default', () => {
      render(<Progress value={50} />);
      expect(screen.queryByText('50%')).not.toBeInTheDocument();
    });

    it('should format custom value', () => {
      render(
        <Progress
          value={50}
          showValue
          formatValue={(value) => `${value} of 100`}
        />
      );
      expect(screen.getByText('50 of 100')).toBeInTheDocument();
    });
  });

  describe('Sizes', () => {
    it('should render small progress bar', () => {
      const { container } = render(<Progress value={50} size="sm" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('size-sm');
    });

    it('should render medium progress bar', () => {
      const { container } = render(<Progress value={50} size="md" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('size-md');
    });

    it('should render large progress bar', () => {
      const { container } = render(<Progress value={50} size="lg" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('size-lg');
    });

    it('should use medium size by default', () => {
      const { container } = render(<Progress value={50} />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('size-md');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Progress value={50} colorScheme="primary" />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      const { container } = render(<Progress value={50} colorScheme="success" />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('color-success');
    });

    it('should render with warning color', () => {
      const { container } = render(<Progress value={50} colorScheme="warning" />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('color-warning');
    });

    it('should render with error color', () => {
      const { container } = render(<Progress value={50} colorScheme="error" />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('color-error');
    });

    it('should use primary color by default', () => {
      const { container } = render(<Progress value={50} />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('color-primary');
    });
  });

  describe('Variants', () => {
    it('should render linear variant', () => {
      const { container } = render(<Progress value={50} variant="linear" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('variant-linear');
    });

    it('should render circular variant', () => {
      const { container } = render(<Progress value={50} variant="circular" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('variant-circular');
    });

    it('should use linear variant by default', () => {
      const { container } = render(<Progress value={50} />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('variant-linear');
    });
  });

  describe('Striped Pattern', () => {
    it('should render with striped pattern', () => {
      const { container } = render(<Progress value={50} striped />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('striped');
    });

    it('should not be striped by default', () => {
      const { container } = render(<Progress value={50} />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).not.toHaveClass('striped');
    });
  });

  describe('Animation', () => {
    it('should animate when animated prop is true', () => {
      const { container } = render(<Progress value={50} animated />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('animated');
    });

    it('should animate striped pattern', () => {
      const { container } = render(<Progress value={50} striped animated />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('striped', 'animated');
    });

    it('should not animate by default', () => {
      const { container } = render(<Progress value={50} />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).not.toHaveClass('animated');
    });
  });

  describe('Indeterminate State', () => {
    it('should render indeterminate progress', () => {
      const { container } = render(<Progress indeterminate />);
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveClass('indeterminate');
    });

    it('should ignore value when indeterminate', () => {
      render(<Progress value={50} indeterminate showValue />);
      expect(screen.queryByText('50%')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have role="progressbar"', () => {
      render(<Progress value={50} />);
      const progress = screen.getByRole('progressbar');
      expect(progress).toBeInTheDocument();
    });

    it('should have aria-valuenow', () => {
      render(<Progress value={75} />);
      const progress = screen.getByRole('progressbar');
      expect(progress).toHaveAttribute('aria-valuenow', '75');
    });

    it('should have aria-valuemin', () => {
      render(<Progress value={50} />);
      const progress = screen.getByRole('progressbar');
      expect(progress).toHaveAttribute('aria-valuemin', '0');
    });

    it('should have aria-valuemax', () => {
      render(<Progress value={50} />);
      const progress = screen.getByRole('progressbar');
      expect(progress).toHaveAttribute('aria-valuemax', '100');
    });

    it('should support custom aria-label', () => {
      render(<Progress value={50} aria-label="Upload progress" />);
      const progress = screen.getByLabelText('Upload progress');
      expect(progress).toBeInTheDocument();
    });

    it('should use label as aria-label when provided', () => {
      render(<Progress value={50} label="Loading data" />);
      const progress = screen.getByRole('progressbar');
      expect(progress).toHaveAttribute('aria-label', 'Loading data');
    });

    it('should not have aria-valuenow when indeterminate', () => {
      render(<Progress indeterminate />);
      const progress = screen.getByRole('progressbar');
      expect(progress).not.toHaveAttribute('aria-valuenow');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Progress value={50} className="custom-progress" />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('custom-progress');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Progress value={50} style={{ height: '20px' }} />
      );
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveStyle({ height: '20px' });
    });
  });

  describe('Track Color', () => {
    it('should render with custom track color', () => {
      const { container } = render(<Progress value={50} trackColor="gray" />);
      const track = container.querySelector('[data-testid="progress-track"]');
      expect(track).toHaveClass('track-color-gray');
    });
  });

  describe('Rounded Corners', () => {
    it('should render with rounded corners', () => {
      const { container } = render(<Progress value={50} rounded />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).toHaveClass('rounded');
    });

    it('should not be rounded by default', () => {
      const { container } = render(<Progress value={50} />);
      const progress = container.querySelector('[role="progressbar"]');
      expect(progress).not.toHaveClass('rounded');
    });
  });

  describe('Multiple Segments', () => {
    it('should render progress with multiple segments', () => {
      render(
        <Progress
          segments={[
            { value: 30, colorScheme: 'success' },
            { value: 20, colorScheme: 'warning' },
            { value: 10, colorScheme: 'error' },
          ]}
        />
      );
      
      const segments = screen.getAllByTestId(/progress-segment/);
      expect(segments).toHaveLength(3);
    });

    it('should calculate total from segments', () => {
      render(
        <Progress
          segments={[
            { value: 30, colorScheme: 'success' },
            { value: 20, colorScheme: 'warning' },
          ]}
          showValue
        />
      );
      
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('Transitions', () => {
    it('should transition smoothly when value changes', () => {
      const { rerender, container } = render(<Progress value={30} />);
      
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveStyle({ width: '30%' });
      
      rerender(<Progress value={70} />);
      
      expect(progressBar).toHaveStyle({ width: '70%' });
    });

    it('should support custom transition duration', () => {
      const { container } = render(
        <Progress value={50} transitionDuration="2s" />
      );
      
      const progressBar = container.querySelector('[data-testid="progress-bar"]');
      expect(progressBar).toHaveStyle({ transitionDuration: '2s' });
    });
  });

  describe('Circular Progress', () => {
    it('should render circular progress with correct value', () => {
      const { container } = render(
        <Progress value={75} variant="circular" />
      );
      
      const circle = container.querySelector('circle[data-testid="progress-circle"]');
      expect(circle).toBeInTheDocument();
    });

    it('should show value in center of circular progress', () => {
      render(
        <Progress value={75} variant="circular" showValue />
      );
      
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('should support custom thickness for circular progress', () => {
      const { container } = render(
        <Progress value={50} variant="circular" thickness={8} />
      );
      
      const circle = container.querySelector('circle[data-testid="progress-circle"]');
      expect(circle).toHaveAttribute('stroke-width', '8');
    });
  });
});
