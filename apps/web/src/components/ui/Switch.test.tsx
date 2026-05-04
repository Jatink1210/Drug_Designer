/**
 * Unit tests for Switch component
 * 
 * Tests toggle switch functionality including:
 * - Rendering and display
 * - On/off states
 * - Disabled state
 * - Labels and accessibility
 * - Animations
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Switch } from './Switch';

describe('Switch Component', () => {
  describe('Rendering', () => {
    it('should render switch', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Switch label="Enable notifications" />);
      expect(screen.getByText('Enable notifications')).toBeInTheDocument();
    });

    it('should render without label', () => {
      render(<Switch />);
      expect(screen.queryByText(/enable/i)).not.toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <Switch
          label="Dark Mode"
          description="Switch to dark theme"
        />
      );
      
      expect(screen.getByText('Dark Mode')).toBeInTheDocument();
      expect(screen.getByText('Switch to dark theme')).toBeInTheDocument();
    });
  });

  describe('Toggle State', () => {
    it('should be off by default', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.checked).toBe(false);
    });

    it('should render as on when checked prop is true', () => {
      render(<Switch checked />);
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.checked).toBe(true);
    });

    it('should toggle state on click', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      
      expect(switchElement.checked).toBe(false);
      
      fireEvent.click(switchElement);
      expect(switchElement.checked).toBe(true);
      
      fireEvent.click(switchElement);
      expect(switchElement.checked).toBe(false);
    });

    it('should call onChange when toggled', () => {
      const mockOnChange = jest.fn();
      render(<Switch onChange={mockOnChange} />);
      
      const switchElement = screen.getByRole('switch');
      fireEvent.click(switchElement);
      
      expect(mockOnChange).toHaveBeenCalledTimes(1);
      expect(mockOnChange).toHaveBeenCalledWith(true);
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Switch checked={false} onChange={mockOnChange} />
      );
      
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.checked).toBe(false);
      
      fireEvent.click(switchElement);
      expect(mockOnChange).toHaveBeenCalledWith(true);
      
      rerender(<Switch checked={true} onChange={mockOnChange} />);
      expect(switchElement.checked).toBe(true);
    });
  });

  describe('Disabled State', () => {
    it('should render disabled switch', () => {
      render(<Switch disabled />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeDisabled();
    });

    it('should not be disabled by default', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).not.toBeDisabled();
    });

    it('should not call onChange when disabled', () => {
      const mockOnChange = jest.fn();
      render(<Switch disabled onChange={mockOnChange} />);
      
      const switchElement = screen.getByRole('switch');
      fireEvent.click(switchElement);
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('should have disabled styling', () => {
      const { container } = render(<Switch disabled label="Disabled" />);
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('disabled');
    });
  });

  describe('Sizes', () => {
    it('should render small switch', () => {
      const { container } = render(<Switch size="sm" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('size-sm');
    });

    it('should render medium switch', () => {
      const { container } = render(<Switch size="md" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('size-md');
    });

    it('should render large switch', () => {
      const { container } = render(<Switch size="lg" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('size-lg');
    });

    it('should use medium size by default', () => {
      const { container } = render(<Switch />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('size-md');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Switch colorScheme="primary" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      const { container } = render(<Switch colorScheme="success" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('color-success');
    });

    it('should render with error color', () => {
      const { container } = render(<Switch colorScheme="error" />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('color-error');
    });

    it('should use primary color by default', () => {
      const { container } = render(<Switch />);
      const switchElement = container.querySelector('.switch');
      expect(switchElement).toHaveClass('color-primary');
    });
  });

  describe('Label Positioning', () => {
    it('should render label on the right by default', () => {
      const { container } = render(<Switch label="Right label" />);
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('label-right');
    });

    it('should render label on the left', () => {
      const { container } = render(
        <Switch label="Left label" labelPosition="left" />
      );
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('label-left');
    });
  });

  describe('Accessibility', () => {
    it('should have role="switch"', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeInTheDocument();
    });

    it('should have aria-checked="false" when off', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('should have aria-checked="true" when on', () => {
      render(<Switch checked />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
    });

    it('should have aria-disabled when disabled', () => {
      render(<Switch disabled />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-disabled', 'true');
    });

    it('should support aria-label', () => {
      render(<Switch aria-label="Toggle dark mode" />);
      const switchElement = screen.getByLabelText('Toggle dark mode');
      expect(switchElement).toBeInTheDocument();
    });

    it('should use label as aria-label when provided', () => {
      render(<Switch label="Dark Mode" />);
      const switchElement = screen.getByLabelText('Dark Mode');
      expect(switchElement).toBeInTheDocument();
    });

    it('should support aria-describedby', () => {
      render(
        <>
          <Switch aria-describedby="switch-description" />
          <div id="switch-description">This is a description</div>
        </>
      );
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-describedby', 'switch-description');
    });

    it('should be keyboard accessible', () => {
      const mockOnChange = jest.fn();
      render(<Switch onChange={mockOnChange} />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      
      expect(switchElement).toHaveFocus();
      
      fireEvent.keyDown(switchElement, { key: ' ' });
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe('Animation', () => {
    it('should animate toggle transition', async () => {
      const { container } = render(<Switch />);
      const switchElement = screen.getByRole('switch');
      const thumb = container.querySelector('.switch-thumb');
      
      fireEvent.click(switchElement);
      
      await waitFor(() => {
        expect(thumb).toHaveClass('checked');
      });
    });

    it('should have smooth transition', () => {
      const { container } = render(<Switch />);
      const thumb = container.querySelector('.switch-thumb');
      
      const styles = window.getComputedStyle(thumb!);
      expect(styles.transition).toContain('transform');
    });
  });

  describe('Loading State', () => {
    it('should render loading state', () => {
      const { container } = render(<Switch loading />);
      const spinner = container.querySelector('.switch-spinner');
      expect(spinner).toBeInTheDocument();
    });

    it('should disable switch when loading', () => {
      render(<Switch loading />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeDisabled();
    });

    it('should not call onChange when loading', () => {
      const mockOnChange = jest.fn();
      render(<Switch loading onChange={mockOnChange} />);
      
      const switchElement = screen.getByRole('switch');
      fireEvent.click(switchElement);
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  describe('Icons', () => {
    it('should render with custom icons', () => {
      const { container } = render(
        <Switch
          checkedIcon={<span data-testid="check-icon">✓</span>}
          uncheckedIcon={<span data-testid="x-icon">✗</span>}
        />
      );
      
      expect(screen.getByTestId('x-icon')).toBeInTheDocument();
    });

    it('should show checked icon when on', () => {
      const { container } = render(
        <Switch
          checked
          checkedIcon={<span data-testid="check-icon">✓</span>}
          uncheckedIcon={<span data-testid="x-icon">✗</span>}
        />
      );
      
      expect(screen.getByTestId('check-icon')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<Switch error />);
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<Switch error errorMessage="This field is required" />);
      expect(screen.getByText('This field is required')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      render(<Switch error />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(<Switch label="Required field" required />);
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required when required', () => {
      render(<Switch required />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Switch className="custom-switch" />);
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('custom-switch');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Switch style={{ margin: '20px' }} />
      );
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Name and Value Props', () => {
    it('should have name attribute', () => {
      render(<Switch name="darkMode" />);
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.name).toBe('darkMode');
    });

    it('should have value attribute', () => {
      render(<Switch value="enabled" />);
      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.value).toBe('enabled');
    });
  });

  describe('ID Prop', () => {
    it('should have id attribute', () => {
      render(<Switch id="custom-id" />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('id', 'custom-id');
    });

    it('should generate id automatically if not provided', () => {
      render(<Switch />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('id');
    });
  });

  describe('Focus Management', () => {
    it('should support autoFocus', () => {
      render(<Switch autoFocus />);
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveFocus();
    });

    it('should show focus indicator when focused', () => {
      const { container } = render(<Switch />);
      const switchElement = screen.getByRole('switch');
      
      switchElement.focus();
      
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).toHaveClass('focused');
    });

    it('should remove focus indicator on blur', () => {
      const { container } = render(<Switch />);
      const switchElement = screen.getByRole('switch');
      
      switchElement.focus();
      switchElement.blur();
      
      const wrapper = container.querySelector('.switch-wrapper');
      expect(wrapper).not.toHaveClass('focused');
    });
  });

  describe('Callback Props', () => {
    it('should call onFocus when focused', () => {
      const mockOnFocus = jest.fn();
      render(<Switch onFocus={mockOnFocus} />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      
      expect(mockOnFocus).toHaveBeenCalled();
    });

    it('should call onBlur when blurred', () => {
      const mockOnBlur = jest.fn();
      render(<Switch onBlur={mockOnBlur} />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      switchElement.blur();
      
      expect(mockOnBlur).toHaveBeenCalled();
    });
  });

  describe('Ref Forwarding', () => {
    it('should forward ref to input element', () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<Switch ref={ref} />);
      
      expect(ref.current).toBeInstanceOf(HTMLInputElement);
      expect(ref.current?.type).toBe('checkbox');
    });
  });
});
