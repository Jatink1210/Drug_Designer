/**
 * Unit tests for Slider component
 * 
 * Tests slider functionality including:
 * - Rendering and display
 * - Value changes
 * - Range slider
 * - Disabled state
 * - Marks and labels
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Slider } from './Slider';

describe('Slider Component', () => {
  describe('Rendering', () => {
    it('should render slider', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider');
      expect(slider).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Slider label="Volume" />);
      expect(screen.getByText('Volume')).toBeInTheDocument();
    });

    it('should render without label', () => {
      render(<Slider />);
      expect(screen.queryByText(/volume/i)).not.toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <Slider
          label="Volume"
          description="Adjust the volume level"
        />
      );
      
      expect(screen.getByText('Adjust the volume level')).toBeInTheDocument();
    });
  });

  describe('Value', () => {
    it('should have default value of 0', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.value).toBe('0');
    });

    it('should render with initial value', () => {
      render(<Slider defaultValue={50} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.value).toBe('50');
    });

    it('should update value on change', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      
      fireEvent.change(slider, { target: { value: '75' } });
      expect(slider.value).toBe('75');
    });

    it('should call onChange when value changes', () => {
      const mockOnChange = jest.fn();
      render(<Slider onChange={mockOnChange} />);
      
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '50' } });
      
      expect(mockOnChange).toHaveBeenCalledWith(50);
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Slider value={25} onChange={mockOnChange} />
      );
      
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.value).toBe('25');
      
      fireEvent.change(slider, { target: { value: '75' } });
      expect(mockOnChange).toHaveBeenCalledWith(75);
      
      rerender(<Slider value={75} onChange={mockOnChange} />);
      expect(slider.value).toBe('75');
    });
  });

  describe('Min/Max', () => {
    it('should have default min of 0', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.min).toBe('0');
    });

    it('should have default max of 100', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.max).toBe('100');
    });

    it('should render with custom min', () => {
      render(<Slider min={10} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.min).toBe('10');
    });

    it('should render with custom max', () => {
      render(<Slider max={200} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.max).toBe('200');
    });

    it('should clamp value to min', () => {
      render(<Slider min={10} defaultValue={5} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(parseInt(slider.value)).toBeGreaterThanOrEqual(10);
    });

    it('should clamp value to max', () => {
      render(<Slider max={100} defaultValue={150} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(parseInt(slider.value)).toBeLessThanOrEqual(100);
    });
  });

  describe('Step', () => {
    it('should have default step of 1', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.step).toBe('1');
    });

    it('should render with custom step', () => {
      render(<Slider step={5} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      expect(slider.step).toBe('5');
    });

    it('should snap to step values', () => {
      render(<Slider step={10} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      
      fireEvent.change(slider, { target: { value: '23' } });
      expect(parseInt(slider.value) % 10).toBe(0);
    });
  });

  describe('Disabled State', () => {
    it('should render disabled slider', () => {
      render(<Slider disabled />);
      const slider = screen.getByRole('slider');
      expect(slider).toBeDisabled();
    });

    it('should not be disabled by default', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider');
      expect(slider).not.toBeDisabled();
    });

    it('should not call onChange when disabled', () => {
      const mockOnChange = jest.fn();
      render(<Slider disabled onChange={mockOnChange} />);
      
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '50' } });
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('should have disabled styling', () => {
      const { container } = render(<Slider disabled />);
      const wrapper = container.querySelector('.slider-wrapper');
      expect(wrapper).toHaveClass('disabled');
    });
  });

  describe('Orientation', () => {
    it('should be horizontal by default', () => {
      const { container } = render(<Slider />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('horizontal');
    });

    it('should render vertical slider', () => {
      const { container } = render(<Slider orientation="vertical" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('vertical');
    });
  });

  describe('Marks', () => {
    it('should render marks', () => {
      const marks = [
        { value: 0, label: '0' },
        { value: 50, label: '50' },
        { value: 100, label: '100' }
      ];
      
      render(<Slider marks={marks} />);
      
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument();
      expect(screen.getByText('100')).toBeInTheDocument();
    });

    it('should render marks without labels', () => {
      const marks = [
        { value: 0 },
        { value: 50 },
        { value: 100 }
      ];
      
      const { container } = render(<Slider marks={marks} />);
      const markElements = container.querySelectorAll('.slider-mark');
      expect(markElements).toHaveLength(3);
    });
  });

  describe('Value Display', () => {
    it('should show value when showValue is true', () => {
      render(<Slider defaultValue={50} showValue />);
      expect(screen.getByText('50')).toBeInTheDocument();
    });

    it('should not show value by default', () => {
      render(<Slider defaultValue={50} />);
      expect(screen.queryByText('50')).not.toBeInTheDocument();
    });

    it('should format value with custom formatter', () => {
      const formatter = (value: number) => `${value}%`;
      render(<Slider defaultValue={50} showValue valueFormatter={formatter} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('Sizes', () => {
    it('should render small slider', () => {
      const { container } = render(<Slider size="sm" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('size-sm');
    });

    it('should render medium slider', () => {
      const { container } = render(<Slider size="md" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('size-md');
    });

    it('should render large slider', () => {
      const { container } = render(<Slider size="lg" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('size-lg');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Slider colorScheme="primary" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      const { container } = render(<Slider colorScheme="success" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('color-success');
    });

    it('should render with error color', () => {
      const { container } = render(<Slider colorScheme="error" />);
      const slider = container.querySelector('.slider');
      expect(slider).toHaveClass('color-error');
    });
  });

  describe('Accessibility', () => {
    it('should have role="slider"', () => {
      render(<Slider />);
      const slider = screen.getByRole('slider');
      expect(slider).toBeInTheDocument();
    });

    it('should have aria-valuemin', () => {
      render(<Slider min={10} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuemin', '10');
    });

    it('should have aria-valuemax', () => {
      render(<Slider max={200} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuemax', '200');
    });

    it('should have aria-valuenow', () => {
      render(<Slider defaultValue={50} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuenow', '50');
    });

    it('should have aria-valuetext when formatter is provided', () => {
      const formatter = (value: number) => `${value}%`;
      render(<Slider defaultValue={50} valueFormatter={formatter} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuetext', '50%');
    });

    it('should have aria-label', () => {
      render(<Slider aria-label="Volume control" />);
      const slider = screen.getByLabelText('Volume control');
      expect(slider).toBeInTheDocument();
    });

    it('should use label as aria-label when provided', () => {
      render(<Slider label="Volume" />);
      const slider = screen.getByLabelText('Volume');
      expect(slider).toBeInTheDocument();
    });

    it('should have aria-disabled when disabled', () => {
      render(<Slider disabled />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-disabled', 'true');
    });

    it('should be keyboard accessible', () => {
      render(<Slider defaultValue={50} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      
      slider.focus();
      expect(slider).toHaveFocus();
      
      fireEvent.keyDown(slider, { key: 'ArrowRight' });
      expect(parseInt(slider.value)).toBeGreaterThan(50);
      
      fireEvent.keyDown(slider, { key: 'ArrowLeft' });
      expect(parseInt(slider.value)).toBeLessThan(51);
    });

    it('should support Home key', () => {
      render(<Slider defaultValue={50} min={0} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      
      fireEvent.keyDown(slider, { key: 'Home' });
      expect(slider.value).toBe('0');
    });

    it('should support End key', () => {
      render(<Slider defaultValue={50} max={100} />);
      const slider = screen.getByRole('slider') as HTMLInputElement;
      
      fireEvent.keyDown(slider, { key: 'End' });
      expect(slider.value).toBe('100');
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<Slider error />);
      const wrapper = container.querySelector('.slider-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<Slider error errorMessage="Value out of range" />);
      expect(screen.getByText('Value out of range')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      render(<Slider error />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Slider className="custom-slider" />);
      const wrapper = container.querySelector('.slider-wrapper');
      expect(wrapper).toHaveClass('custom-slider');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Slider style={{ margin: '20px' }} />
      );
      const wrapper = container.querySelector('.slider-wrapper');
      expect(wrapper).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Callbacks', () => {
    it('should call onChangeStart when dragging starts', () => {
      const mockOnChangeStart = jest.fn();
      render(<Slider onChangeStart={mockOnChangeStart} />);
      
      const slider = screen.getByRole('slider');
      fireEvent.mouseDown(slider);
      
      expect(mockOnChangeStart).toHaveBeenCalled();
    });

    it('should call onChangeEnd when dragging ends', () => {
      const mockOnChangeEnd = jest.fn();
      render(<Slider onChangeEnd={mockOnChangeEnd} />);
      
      const slider = screen.getByRole('slider');
      fireEvent.mouseDown(slider);
      fireEvent.mouseUp(slider);
      
      expect(mockOnChangeEnd).toHaveBeenCalled();
    });
  });
});
