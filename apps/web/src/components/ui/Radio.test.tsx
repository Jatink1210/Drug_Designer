/**
 * Unit tests for Radio component
 * 
 * Tests radio button functionality including:
 * - Rendering and display
 * - Selection states
 * - Radio groups
 * - Disabled state
 * - Labels and accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Radio, RadioGroup } from './Radio';

describe('Radio Component', () => {
  describe('Rendering', () => {
    it('should render radio button', () => {
      render(<Radio />);
      const radio = screen.getByRole('radio');
      expect(radio).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<Radio label="Option A" />);
      expect(screen.getByText('Option A')).toBeInTheDocument();
    });

    it('should render without label', () => {
      render(<Radio />);
      expect(screen.queryByText(/option/i)).not.toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <Radio
          label="Premium Plan"
          description="Includes all features"
        />
      );
      
      expect(screen.getByText('Premium Plan')).toBeInTheDocument();
      expect(screen.getByText('Includes all features')).toBeInTheDocument();
    });
  });

  describe('Selection State', () => {
    it('should be unselected by default', () => {
      render(<Radio />);
      const radio = screen.getByRole('radio') as HTMLInputElement;
      expect(radio.checked).toBe(false);
    });

    it('should render as selected when checked prop is true', () => {
      render(<Radio checked />);
      const radio = screen.getByRole('radio') as HTMLInputElement;
      expect(radio.checked).toBe(true);
    });

    it('should call onChange when clicked', () => {
      const mockOnChange = jest.fn();
      render(<Radio onChange={mockOnChange} />);
      
      const radio = screen.getByRole('radio');
      fireEvent.click(radio);
      
      expect(mockOnChange).toHaveBeenCalledTimes(1);
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Radio checked={false} onChange={mockOnChange} />
      );
      
      const radio = screen.getByRole('radio') as HTMLInputElement;
      expect(radio.checked).toBe(false);
      
      fireEvent.click(radio);
      expect(mockOnChange).toHaveBeenCalled();
      
      rerender(<Radio checked={true} onChange={mockOnChange} />);
      expect(radio.checked).toBe(true);
    });
  });

  describe('Disabled State', () => {
    it('should render disabled radio', () => {
      render(<Radio disabled />);
      const radio = screen.getByRole('radio');
      expect(radio).toBeDisabled();
    });

    it('should not be disabled by default', () => {
      render(<Radio />);
      const radio = screen.getByRole('radio');
      expect(radio).not.toBeDisabled();
    });

    it('should not call onChange when disabled', () => {
      const mockOnChange = jest.fn();
      render(<Radio disabled onChange={mockOnChange} />);
      
      const radio = screen.getByRole('radio');
      fireEvent.click(radio);
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('should have disabled styling', () => {
      const { container } = render(<Radio disabled label="Disabled" />);
      const label = container.querySelector('label');
      expect(label).toHaveClass('disabled');
    });
  });

  describe('Sizes', () => {
    it('should render small radio', () => {
      const { container } = render(<Radio size="sm" />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('size-sm');
    });

    it('should render medium radio', () => {
      const { container } = render(<Radio size="md" />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('size-md');
    });

    it('should render large radio', () => {
      const { container } = render(<Radio size="lg" />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('size-lg');
    });

    it('should use medium size by default', () => {
      const { container } = render(<Radio />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('size-md');
    });
  });

  describe('Colors', () => {
    it('should render with primary color', () => {
      const { container } = render(<Radio colorScheme="primary" />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('color-primary');
    });

    it('should render with success color', () => {
      const { container } = render(<Radio colorScheme="success" />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('color-success');
    });

    it('should use primary color by default', () => {
      const { container } = render(<Radio />);
      const radio = container.querySelector('input[type="radio"]');
      expect(radio?.parentElement).toHaveClass('color-primary');
    });
  });

  describe('Value Prop', () => {
    it('should have value attribute', () => {
      render(<Radio value="option1" />);
      const radio = screen.getByRole('radio') as HTMLInputElement;
      expect(radio.value).toBe('option1');
    });

    it('should pass value in onChange event', () => {
      const mockOnChange = jest.fn();
      render(<Radio value="option1" onChange={mockOnChange} />);
      
      const radio = screen.getByRole('radio');
      fireEvent.click(radio);
      
      expect(mockOnChange).toHaveBeenCalledWith(
        expect.objectContaining({
          target: expect.objectContaining({ value: 'option1' })
        })
      );
    });
  });

  describe('Name Prop', () => {
    it('should have name attribute', () => {
      render(<Radio name="plan" />);
      const radio = screen.getByRole('radio') as HTMLInputElement;
      expect(radio.name).toBe('plan');
    });
  });

  describe('Accessibility', () => {
    it('should have role="radio"', () => {
      render(<Radio />);
      const radio = screen.getByRole('radio');
      expect(radio).toBeInTheDocument();
    });

    it('should have aria-checked="false" when unselected', () => {
      render(<Radio />);
      const radio = screen.getByRole('radio');
      expect(radio).toHaveAttribute('aria-checked', 'false');
    });

    it('should have aria-checked="true" when selected', () => {
      render(<Radio checked />);
      const radio = screen.getByRole('radio');
      expect(radio).toHaveAttribute('aria-checked', 'true');
    });

    it('should have aria-disabled when disabled', () => {
      render(<Radio disabled />);
      const radio = screen.getByRole('radio');
      expect(radio).toHaveAttribute('aria-disabled', 'true');
    });

    it('should support aria-label', () => {
      render(<Radio aria-label="Select premium plan" />);
      const radio = screen.getByLabelText('Select premium plan');
      expect(radio).toBeInTheDocument();
    });

    it('should use label as aria-label when provided', () => {
      render(<Radio label="Premium Plan" />);
      const radio = screen.getByLabelText('Premium Plan');
      expect(radio).toBeInTheDocument();
    });

    it('should be keyboard accessible', () => {
      const mockOnChange = jest.fn();
      render(<Radio onChange={mockOnChange} />);
      
      const radio = screen.getByRole('radio');
      radio.focus();
      
      expect(radio).toHaveFocus();
      
      fireEvent.keyDown(radio, { key: ' ' });
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<Radio error />);
      const wrapper = container.querySelector('.radio-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<Radio error errorMessage="Please select an option" />);
      expect(screen.getByText('Please select an option')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      render(<Radio error />);
      const radio = screen.getByRole('radio');
      expect(radio).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(<Radio label="Required field" required />);
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required when required', () => {
      render(<Radio required />);
      const radio = screen.getByRole('radio');
      expect(radio).toHaveAttribute('aria-required', 'true');
    });
  });
});

describe('RadioGroup Component', () => {
  describe('Rendering', () => {
    it('should render radio group', () => {
      render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      const radios = screen.getAllByRole('radio');
      expect(radios).toHaveLength(2);
    });

    it('should render with label', () => {
      render(
        <RadioGroup name="plan" label="Select a plan">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      expect(screen.getByText('Select a plan')).toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <RadioGroup
          name="plan"
          label="Select a plan"
          description="Choose the plan that fits your needs"
        >
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      expect(screen.getByText('Choose the plan that fits your needs')).toBeInTheDocument();
    });
  });

  describe('Selection Management', () => {
    it('should allow only one radio to be selected', () => {
      render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
          <Radio value="enterprise" label="Enterprise" />
        </RadioGroup>
      );
      
      const basic = screen.getByLabelText('Basic') as HTMLInputElement;
      const premium = screen.getByLabelText('Premium') as HTMLInputElement;
      
      fireEvent.click(basic);
      expect(basic.checked).toBe(true);
      expect(premium.checked).toBe(false);
      
      fireEvent.click(premium);
      expect(basic.checked).toBe(false);
      expect(premium.checked).toBe(true);
    });

    it('should call onChange with selected value', () => {
      const mockOnChange = jest.fn();
      render(
        <RadioGroup name="plan" onChange={mockOnChange}>
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      const premium = screen.getByLabelText('Premium');
      fireEvent.click(premium);
      
      expect(mockOnChange).toHaveBeenCalledWith('premium');
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <RadioGroup name="plan" value="basic" onChange={mockOnChange}>
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      const basic = screen.getByLabelText('Basic') as HTMLInputElement;
      const premium = screen.getByLabelText('Premium') as HTMLInputElement;
      
      expect(basic.checked).toBe(true);
      expect(premium.checked).toBe(false);
      
      fireEvent.click(premium);
      expect(mockOnChange).toHaveBeenCalledWith('premium');
      
      rerender(
        <RadioGroup name="plan" value="premium" onChange={mockOnChange}>
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      expect(basic.checked).toBe(false);
      expect(premium.checked).toBe(true);
    });
  });

  describe('Orientation', () => {
    it('should render vertically by default', () => {
      const { container } = render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('.radio-group');
      expect(group).toHaveClass('vertical');
    });

    it('should render horizontally', () => {
      const { container } = render(
        <RadioGroup name="plan" orientation="horizontal">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('.radio-group');
      expect(group).toHaveClass('horizontal');
    });
  });

  describe('Disabled State', () => {
    it('should disable all radios when group is disabled', () => {
      render(
        <RadioGroup name="plan" disabled>
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      const radios = screen.getAllByRole('radio');
      radios.forEach(radio => {
        expect(radio).toBeDisabled();
      });
    });
  });

  describe('Keyboard Navigation', () => {
    it('should navigate with arrow keys', () => {
      render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
          <Radio value="enterprise" label="Enterprise" />
        </RadioGroup>
      );
      
      const basic = screen.getByLabelText('Basic');
      const premium = screen.getByLabelText('Premium');
      
      basic.focus();
      expect(basic).toHaveFocus();
      
      fireEvent.keyDown(basic, { key: 'ArrowDown' });
      expect(premium).toHaveFocus();
    });

    it('should wrap around when navigating', () => {
      render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
          <Radio value="premium" label="Premium" />
        </RadioGroup>
      );
      
      const basic = screen.getByLabelText('Basic');
      const premium = screen.getByLabelText('Premium');
      
      premium.focus();
      fireEvent.keyDown(premium, { key: 'ArrowDown' });
      expect(basic).toHaveFocus();
    });
  });

  describe('Accessibility', () => {
    it('should have role="radiogroup"', () => {
      const { container } = render(
        <RadioGroup name="plan">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('[role="radiogroup"]');
      expect(group).toBeInTheDocument();
    });

    it('should have aria-labelledby when label provided', () => {
      const { container } = render(
        <RadioGroup name="plan" label="Select a plan">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('[role="radiogroup"]');
      expect(group).toHaveAttribute('aria-labelledby');
    });

    it('should have aria-describedby when description provided', () => {
      const { container } = render(
        <RadioGroup
          name="plan"
          label="Select a plan"
          description="Choose wisely"
        >
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('[role="radiogroup"]');
      expect(group).toHaveAttribute('aria-describedby');
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(
        <RadioGroup name="plan" error>
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('.radio-group');
      expect(group).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(
        <RadioGroup name="plan" error errorMessage="Please select a plan">
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      expect(screen.getByText('Please select a plan')).toBeInTheDocument();
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(
        <RadioGroup name="plan" label="Select a plan" required>
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required on group', () => {
      const { container } = render(
        <RadioGroup name="plan" required>
          <Radio value="basic" label="Basic" />
        </RadioGroup>
      );
      
      const group = container.querySelector('[role="radiogroup"]');
      expect(group).toHaveAttribute('aria-required', 'true');
    });
  });
});
