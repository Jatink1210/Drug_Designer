/**
 * Unit tests for Checkbox component
 * 
 * Tests checkbox functionality including:
 * - Rendering and display
 * - Checked/unchecked states
 * - Indeterminate state
 * - Disabled state
 * - Labels and accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Checkbox } from './Checkbox';

describe('Checkbox Component', () => {
  describe('Rendering', () => {
    it('should render checkbox', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Checkbox label="Accept terms" />);
      expect(screen.getByText('Accept terms')).toBeInTheDocument();
    });

    it('should render without label', () => {
      render(<Checkbox />);
      expect(screen.queryByText(/accept/i)).not.toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <Checkbox
          label="Subscribe"
          description="Receive email notifications"
        />
      );
      
      expect(screen.getByText('Subscribe')).toBeInTheDocument();
      expect(screen.getByText('Receive email notifications')).toBeInTheDocument();
    });
  });

  describe('Checked State', () => {
    it('should be unchecked by default', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should render as checked when checked prop is true', () => {
      render(<Checkbox checked />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(true);
    });

    it('should toggle checked state on click', () => {
      const { rerender } = render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      
      expect(checkbox.checked).toBe(false);
      
      fireEvent.click(checkbox);
      expect(checkbox.checked).toBe(true);
      
      fireEvent.click(checkbox);
      expect(checkbox.checked).toBe(false);
    });

    it('should call onChange when clicked', () => {
      const mockOnChange = jest.fn();
      render(<Checkbox onChange={mockOnChange} />);
      
      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);
      
      expect(mockOnChange).toHaveBeenCalledTimes(1);
      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        target: expect.objectContaining({ checked: true })
      }));
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Checkbox checked={false} onChange={mockOnChange} />
      );
      
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
      
      fireEvent.click(checkbox);
      expect(mockOnChange).toHaveBeenCalled();
      
      // Simulate parent component updating the checked prop
      rerender(<Checkbox checked={true} onChange={mockOnChange} />);
      expect(checkbox.checked).toBe(true);
    });
  });

  describe('Indeterminate State', () => {
    it('should render indeterminate checkbox', () => {
      render(<Checkbox indeterminate />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.indeterminate).toBe(true);
    });

    it('should not be indeterminate by default', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.indeterminate).toBe(false);
    });

    it('should have indeterminate aria attribute', () => {
      render(<Checkbox indeterminate />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-checked', 'mixed');
    });

    it('should clear indeterminate state when clicked', () => {
      render(<Checkbox indeterminate />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      
      expect(checkbox.indeterminate).toBe(true);
      
      fireEvent.click(checkbox);
      
      expect(checkbox.indeterminate).toBe(false);
      expect(checkbox.checked).toBe(true);
    });
  });

  describe('Disabled State', () => {
    it('should render disabled checkbox', () => {
      render(<Checkbox disabled />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeDisabled();
    });

    it('should not be disabled by default', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeDisabled();
    });

    it('should not call onChange when disabled', () => {
      const mockOnChange = jest.fn();
      render(<Checkbox disabled onChange={mockOnChange} />);
      
      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('should have disabled styling', () => {
      const { container } = render(<Checkbox disabled label="Disabled" />);
      const label = container.querySelector('label');
      expect(label).toHaveClass('disabled');
    });
  });

  describe('Sizes', () => {
    it('should render small checkbox', () => {
      const { container } = render(<Checkbox size="sm" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('size-sm');
    });

    it('should render medium checkbox', () => {
      const { container } = render(<Checkbox size="md" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('size-md');
    });

    it('should render large checkbox', () => {
      const { container } = render(<Checkbox size="lg" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('size-lg');
    });

    it('should use medium size by default', () => {
      const { container } = render(<Checkbox />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('size-md');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Checkbox colorScheme="primary" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      const { container } = render(<Checkbox colorScheme="success" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('color-success');
    });

    it('should render with error color', () => {
      const { container } = render(<Checkbox colorScheme="error" />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('color-error');
    });

    it('should use primary color by default', () => {
      const { container } = render(<Checkbox />);
      const checkbox = container.querySelector('input[type="checkbox"]');
      expect(checkbox?.parentElement).toHaveClass('color-primary');
    });
  });

  describe('Label Positioning', () => {
    it('should render label on the right by default', () => {
      const { container } = render(<Checkbox label="Right label" />);
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveClass('label-right');
    });

    it('should render label on the left', () => {
      const { container } = render(
        <Checkbox label="Left label" labelPosition="left" />
      );
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveClass('label-left');
    });
  });

  describe('Accessibility', () => {
    it('should have role="checkbox"', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });

    it('should have aria-checked="false" when unchecked', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-checked', 'false');
    });

    it('should have aria-checked="true" when checked', () => {
      render(<Checkbox checked />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-checked', 'true');
    });

    it('should have aria-checked="mixed" when indeterminate', () => {
      render(<Checkbox indeterminate />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-checked', 'mixed');
    });

    it('should have aria-disabled when disabled', () => {
      render(<Checkbox disabled />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-disabled', 'true');
    });

    it('should support aria-label', () => {
      render(<Checkbox aria-label="Accept terms and conditions" />);
      const checkbox = screen.getByLabelText('Accept terms and conditions');
      expect(checkbox).toBeInTheDocument();
    });

    it('should use label as aria-label when provided', () => {
      render(<Checkbox label="Subscribe to newsletter" />);
      const checkbox = screen.getByLabelText('Subscribe to newsletter');
      expect(checkbox).toBeInTheDocument();
    });

    it('should support aria-describedby', () => {
      render(
        <>
          <Checkbox aria-describedby="checkbox-description" />
          <div id="checkbox-description">This is a description</div>
        </>
      );
      
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-describedby', 'checkbox-description');
    });

    it('should be keyboard accessible', () => {
      const mockOnChange = jest.fn();
      render(<Checkbox onChange={mockOnChange} />);
      
      const checkbox = screen.getByRole('checkbox');
      checkbox.focus();
      
      expect(checkbox).toHaveFocus();
      
      fireEvent.keyDown(checkbox, { key: ' ' });
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<Checkbox error />);
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<Checkbox error errorMessage="This field is required" />);
      expect(screen.getByText('This field is required')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      render(<Checkbox error />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(<Checkbox label="Required field" required />);
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required when required', () => {
      render(<Checkbox required />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Checkbox className="custom-checkbox" />);
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveClass('custom-checkbox');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Checkbox style={{ margin: '20px' }} />
      );
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Checkbox Group', () => {
    it('should render multiple checkboxes', () => {
      render(
        <>
          <Checkbox label="Option 1" />
          <Checkbox label="Option 2" />
          <Checkbox label="Option 3" />
        </>
      );
      
      expect(screen.getByLabelText('Option 1')).toBeInTheDocument();
      expect(screen.getByLabelText('Option 2')).toBeInTheDocument();
      expect(screen.getByLabelText('Option 3')).toBeInTheDocument();
    });

    it('should handle independent checkbox states', () => {
      render(
        <>
          <Checkbox label="Option 1" />
          <Checkbox label="Option 2" checked />
          <Checkbox label="Option 3" />
        </>
      );
      
      const checkbox1 = screen.getByLabelText('Option 1') as HTMLInputElement;
      const checkbox2 = screen.getByLabelText('Option 2') as HTMLInputElement;
      const checkbox3 = screen.getByLabelText('Option 3') as HTMLInputElement;
      
      expect(checkbox1.checked).toBe(false);
      expect(checkbox2.checked).toBe(true);
      expect(checkbox3.checked).toBe(false);
    });
  });

  describe('Value Prop', () => {
    it('should have value attribute', () => {
      render(<Checkbox value="option1" />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.value).toBe('option1');
    });

    it('should pass value in onChange event', () => {
      const mockOnChange = jest.fn();
      render(<Checkbox value="option1" onChange={mockOnChange} />);
      
      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);
      
      expect(mockOnChange).toHaveBeenCalledWith(
        expect.objectContaining({
          target: expect.objectContaining({ value: 'option1' })
        })
      );
    });
  });

  describe('Name Prop', () => {
    it('should have name attribute', () => {
      render(<Checkbox name="terms" />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.name).toBe('terms');
    });
  });

  describe('ID Prop', () => {
    it('should have id attribute', () => {
      render(<Checkbox id="custom-id" />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('id', 'custom-id');
    });

    it('should generate id automatically if not provided', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAttribute('id');
    });
  });

  describe('Focus Management', () => {
    it('should support autoFocus', () => {
      render(<Checkbox autoFocus />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveFocus();
    });

    it('should show focus indicator when focused', () => {
      const { container } = render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox');
      
      checkbox.focus();
      
      const wrapper = container.querySelector('.checkbox-wrapper');
      expect(wrapper).toHaveClass('focused');
    });
  });
});
