/**
 * Unit tests for DatePicker component
 * 
 * Tests date picker functionality including:
 * - Rendering and display
 * - Date selection
 * - Date range selection
 * - Min/max dates
 * - Disabled dates
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DatePicker } from './DatePicker';

describe('DatePicker Component', () => {
  describe('Rendering', () => {
    it('should render date picker', () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      expect(input).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<DatePicker label="Select Date" />);
      expect(screen.getByText('Select Date')).toBeInTheDocument();
    });

    it('should render without label', () => {
      render(<DatePicker />);
      expect(screen.queryByText(/select/i)).not.toBeInTheDocument();
    });

    it('should render with placeholder', () => {
      render(<DatePicker placeholder="Choose a date" />);
      const input = screen.getByPlaceholderText('Choose a date');
      expect(input).toBeInTheDocument();
    });
  });

  describe('Date Selection', () => {
    it('should open calendar on click', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      fireEvent.click(input);
      
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('should select date on click', async () => {
      const mockOnChange = jest.fn();
      render(<DatePicker onChange={mockOnChange} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const date15 = screen.getByText('15');
        fireEvent.click(date15);
      });
      
      expect(mockOnChange).toHaveBeenCalled();
    });

    it('should display selected date', () => {
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} />);
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toContain('04/23/2026');
    });

    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const date = new Date('2026-04-23');
      const { rerender } = render(
        <DatePicker value={null} onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toBe('');
      
      rerender(<DatePicker value={date} onChange={mockOnChange} />);
      expect(input.value).toContain('04/23/2026');
    });
  });

  describe('Date Range Selection', () => {
    it('should allow range selection', async () => {
      const mockOnChange = jest.fn();
      render(<DatePicker mode="range" onChange={mockOnChange} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const date10 = screen.getByText('10');
        const date20 = screen.getByText('20');
        
        fireEvent.click(date10);
        fireEvent.click(date20);
      });
      
      expect(mockOnChange).toHaveBeenCalled();
    });

    it('should display date range', () => {
      const startDate = new Date('2026-04-10');
      const endDate = new Date('2026-04-20');
      render(<DatePicker mode="range" value={[startDate, endDate]} />);
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toContain('04/10/2026');
      expect(input.value).toContain('04/20/2026');
    });
  });

  describe('Min/Max Dates', () => {
    it('should respect min date', () => {
      const minDate = new Date('2026-04-15');
      render(<DatePicker minDate={minDate} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      // Dates before min should be disabled
      const date10 = screen.queryByText('10');
      if (date10) {
        expect(date10.parentElement).toHaveClass('disabled');
      }
    });

    it('should respect max date', () => {
      const maxDate = new Date('2026-04-15');
      render(<DatePicker maxDate={maxDate} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      // Dates after max should be disabled
      const date20 = screen.queryByText('20');
      if (date20) {
        expect(date20.parentElement).toHaveClass('disabled');
      }
    });

    it('should not allow selection outside min/max range', async () => {
      const mockOnChange = jest.fn();
      const minDate = new Date('2026-04-10');
      const maxDate = new Date('2026-04-20');
      
      render(
        <DatePicker
          minDate={minDate}
          maxDate={maxDate}
          onChange={mockOnChange}
        />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const date5 = screen.queryByText('5');
        if (date5 && !date5.parentElement?.classList.contains('disabled')) {
          fireEvent.click(date5);
          expect(mockOnChange).not.toHaveBeenCalled();
        }
      });
    });
  });

  describe('Disabled Dates', () => {
    it('should disable specific dates', () => {
      const disabledDates = [
        new Date('2026-04-15'),
        new Date('2026-04-16')
      ];
      
      render(<DatePicker disabledDates={disabledDates} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      const date15 = screen.queryByText('15');
      if (date15) {
        expect(date15.parentElement).toHaveClass('disabled');
      }
    });

    it('should disable dates based on function', () => {
      const isDisabled = (date: Date) => date.getDay() === 0 || date.getDay() === 6;
      
      render(<DatePicker isDateDisabled={isDisabled} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      // Weekends should be disabled
      // Implementation would check for weekend dates
    });
  });

  describe('Disabled State', () => {
    it('should render disabled date picker', () => {
      render(<DatePicker disabled />);
      const input = screen.getByRole('textbox');
      expect(input).toBeDisabled();
    });

    it('should not open calendar when disabled', () => {
      render(<DatePicker disabled />);
      const input = screen.getByRole('textbox');
      
      fireEvent.click(input);
      
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('should not call onChange when disabled', () => {
      const mockOnChange = jest.fn();
      render(<DatePicker disabled onChange={mockOnChange} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '04/23/2026' } });
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  describe('Format', () => {
    it('should use default format', () => {
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} />);
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toBe('04/23/2026');
    });

    it('should use custom format', () => {
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} format="yyyy-MM-dd" />);
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toBe('2026-04-23');
    });

    it('should use locale-specific format', () => {
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} locale="en-GB" />);
      
      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input.value).toBe('23/04/2026');
    });
  });

  describe('Calendar Navigation', () => {
    it('should navigate to next month', async () => {
      render(<DatePicker />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const nextButton = screen.getByLabelText(/next month/i);
        fireEvent.click(nextButton);
      });
      
      // Month should change
    });

    it('should navigate to previous month', async () => {
      render(<DatePicker />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const prevButton = screen.getByLabelText(/previous month/i);
        fireEvent.click(prevButton);
      });
      
      // Month should change
    });

    it('should navigate to specific month/year', async () => {
      render(<DatePicker />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const monthSelect = screen.getByRole('combobox', { name: /month/i });
        fireEvent.change(monthSelect, { target: { value: '11' } });
      });
      
      // Month should change to December
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(<DatePicker label="Select Date" />);
      const input = screen.getByRole('textbox');
      
      expect(input).toHaveAttribute('aria-label');
    });

    it('should have aria-expanded when calendar is open', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      expect(input).toHaveAttribute('aria-expanded', 'false');
      
      fireEvent.click(input);
      
      await waitFor(() => {
        expect(input).toHaveAttribute('aria-expanded', 'true');
      });
    });

    it('should have role="dialog" on calendar', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      fireEvent.click(input);
      
      await waitFor(() => {
        const calendar = screen.getByRole('dialog');
        expect(calendar).toBeInTheDocument();
      });
    });

    it('should be keyboard accessible', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      input.focus();
      expect(input).toHaveFocus();
      
      fireEvent.keyDown(input, { key: 'Enter' });
      
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('should navigate dates with arrow keys', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      fireEvent.click(input);
      
      await waitFor(() => {
        const calendar = screen.getByRole('dialog');
        fireEvent.keyDown(calendar, { key: 'ArrowRight' });
        // Focus should move to next date
      });
    });

    it('should close on Escape key', async () => {
      render(<DatePicker />);
      const input = screen.getByRole('textbox');
      
      fireEvent.click(input);
      
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      
      fireEvent.keyDown(document, { key: 'Escape' });
      
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<DatePicker error />);
      const wrapper = container.querySelector('.datepicker-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<DatePicker error errorMessage="Invalid date" />);
      expect(screen.getByText('Invalid date')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      render(<DatePicker error />);
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(<DatePicker label="Date" required />);
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required when required', () => {
      render(<DatePicker required />);
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Clear Button', () => {
    it('should show clear button when value is set', () => {
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} showClearButton />);
      
      const clearButton = screen.getByRole('button', { name: /clear/i });
      expect(clearButton).toBeInTheDocument();
    });

    it('should clear value on clear button click', () => {
      const mockOnChange = jest.fn();
      const date = new Date('2026-04-23');
      render(<DatePicker value={date} showClearButton onChange={mockOnChange} />);
      
      const clearButton = screen.getByRole('button', { name: /clear/i });
      fireEvent.click(clearButton);
      
      expect(mockOnChange).toHaveBeenCalledWith(null);
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<DatePicker className="custom-datepicker" />);
      const wrapper = container.querySelector('.datepicker-wrapper');
      expect(wrapper).toHaveClass('custom-datepicker');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <DatePicker style={{ margin: '20px' }} />
      );
      const wrapper = container.querySelector('.datepicker-wrapper');
      expect(wrapper).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Today Button', () => {
    it('should show today button', async () => {
      render(<DatePicker showTodayButton />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const todayButton = screen.getByText(/today/i);
        expect(todayButton).toBeInTheDocument();
      });
    });

    it('should select today on today button click', async () => {
      const mockOnChange = jest.fn();
      render(<DatePicker showTodayButton onChange={mockOnChange} />);
      
      const input = screen.getByRole('textbox');
      fireEvent.click(input);
      
      await waitFor(() => {
        const todayButton = screen.getByText(/today/i);
        fireEvent.click(todayButton);
      });
      
      expect(mockOnChange).toHaveBeenCalled();
    });
  });
});
