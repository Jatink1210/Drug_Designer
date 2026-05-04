/**
 * Unit tests for Pagination component
 * 
 * Tests pagination functionality including:
 * - Rendering and display
 * - Page navigation
 * - Page size selection
 * - Disabled state
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Pagination } from './Pagination';

describe('Pagination Component', () => {
  describe('Rendering', () => {
    it('should render pagination', () => {
      render(<Pagination total={100} />);
      const pagination = screen.getByRole('navigation');
      expect(pagination).toBeInTheDocument();
    });

    it('should render page numbers', () => {
      render(<Pagination total={50} pageSize={10} />);
      
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('should render previous and next buttons', () => {
      render(<Pagination total={100} />);
      
      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('should render first and last buttons when showFirstLast is true', () => {
      render(<Pagination total={100} showFirstLast />);
      
      expect(screen.getByRole('button', { name: /first/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /last/i })).toBeInTheDocument();
    });
  });

  describe('Page Navigation', () => {
    it('should start on page 1 by default', () => {
      render(<Pagination total={100} />);
      const page1 = screen.getByText('1');
      expect(page1.parentElement).toHaveClass('active');
    });

    it('should navigate to next page', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} onChange={mockOnChange} />);
      
      const nextButton = screen.getByRole('button', { name: /next/i });
      fireEvent.click(nextButton);
      
      expect(mockOnChange).toHaveBeenCalledWith(2);
    });

    it('should navigate to previous page', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} current={3} onChange={mockOnChange} />);
      
      const prevButton = screen.getByRole('button', { name: /previous/i });
      fireEvent.click(prevButton);
      
      expect(mockOnChange).toHaveBeenCalledWith(2);
    });

    it('should navigate to specific page', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} onChange={mockOnChange} />);
      
      const page5 = screen.getByText('5');
      fireEvent.click(page5);
      
      expect(mockOnChange).toHaveBeenCalledWith(5);
    });

    it('should navigate to first page', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} current={5} showFirstLast onChange={mockOnChange} />);
      
      const firstButton = screen.getByRole('button', { name: /first/i });
      fireEvent.click(firstButton);
      
      expect(mockOnChange).toHaveBeenCalledWith(1);
    });

    it('should navigate to last page', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} pageSize={10} showFirstLast onChange={mockOnChange} />);
      
      const lastButton = screen.getByRole('button', { name: /last/i });
      fireEvent.click(lastButton);
      
      expect(mockOnChange).toHaveBeenCalledWith(10);
    });
  });

  describe('Disabled States', () => {
    it('should disable previous button on first page', () => {
      render(<Pagination total={100} current={1} />);
      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toBeDisabled();
    });

    it('should disable next button on last page', () => {
      render(<Pagination total={100} pageSize={10} current={10} />);
      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });

    it('should disable first button on first page', () => {
      render(<Pagination total={100} current={1} showFirstLast />);
      const firstButton = screen.getByRole('button', { name: /first/i });
      expect(firstButton).toBeDisabled();
    });

    it('should disable last button on last page', () => {
      render(<Pagination total={100} pageSize={10} current={10} showFirstLast />);
      const lastButton = screen.getByRole('button', { name: /last/i });
      expect(lastButton).toBeDisabled();
    });

    it('should disable all buttons when disabled prop is true', () => {
      render(<Pagination total={100} disabled />);
      
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('Page Size', () => {
    it('should use default page size of 10', () => {
      render(<Pagination total={100} />);
      // Should have 10 pages (100 / 10)
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('should use custom page size', () => {
      render(<Pagination total={100} pageSize={20} />);
      // Should have 5 pages (100 / 20)
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('should show page size selector when showSizeChanger is true', () => {
      render(<Pagination total={100} showSizeChanger />);
      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();
    });

    it('should change page size', () => {
      const mockOnPageSizeChange = jest.fn();
      render(<Pagination total={100} showSizeChanger onPageSizeChange={mockOnPageSizeChange} />);
      
      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: '20' } });
      
      expect(mockOnPageSizeChange).toHaveBeenCalledWith(20);
    });
  });

  describe('Ellipsis', () => {
    it('should show ellipsis for many pages', () => {
      render(<Pagination total={1000} pageSize={10} />);
      const ellipsis = screen.getAllByText('...');
      expect(ellipsis.length).toBeGreaterThan(0);
    });

    it('should not show ellipsis for few pages', () => {
      render(<Pagination total={50} pageSize={10} />);
      const ellipsis = screen.queryAllByText('...');
      expect(ellipsis.length).toBe(0);
    });
  });

  describe('Total Display', () => {
    it('should show total count when showTotal is true', () => {
      render(<Pagination total={100} showTotal />);
      expect(screen.getByText(/100 items/i)).toBeInTheDocument();
    });

    it('should use custom total renderer', () => {
      const totalRenderer = (total: number) => `Total: ${total}`;
      render(<Pagination total={100} showTotal totalRenderer={totalRenderer} />);
      expect(screen.getByText('Total: 100')).toBeInTheDocument();
    });

    it('should show range when showTotal is true', () => {
      render(<Pagination total={100} current={2} pageSize={10} showTotal />);
      expect(screen.getByText(/11-20 of 100/i)).toBeInTheDocument();
    });
  });

  describe('Sizes', () => {
    it('should render small pagination', () => {
      const { container } = render(<Pagination total={100} size="sm" />);
      const pagination = container.querySelector('.pagination');
      expect(pagination).toHaveClass('size-sm');
    });

    it('should render medium pagination', () => {
      const { container } = render(<Pagination total={100} size="md" />);
      const pagination = container.querySelector('.pagination');
      expect(pagination).toHaveClass('size-md');
    });

    it('should render large pagination', () => {
      const { container } = render(<Pagination total={100} size="lg" />);
      const pagination = container.querySelector('.pagination');
      expect(pagination).toHaveClass('size-lg');
    });
  });

  describe('Accessibility', () => {
    it('should have role="navigation"', () => {
      render(<Pagination total={100} />);
      const pagination = screen.getByRole('navigation');
      expect(pagination).toBeInTheDocument();
    });

    it('should have aria-label', () => {
      render(<Pagination total={100} />);
      const pagination = screen.getByRole('navigation');
      expect(pagination).toHaveAttribute('aria-label', 'Pagination');
    });

    it('should have aria-current on current page', () => {
      render(<Pagination total={100} current={3} />);
      const page3 = screen.getByText('3');
      expect(page3.parentElement).toHaveAttribute('aria-current', 'page');
    });

    it('should have aria-disabled on disabled buttons', () => {
      render(<Pagination total={100} current={1} />);
      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toHaveAttribute('aria-disabled', 'true');
    });

    it('should be keyboard accessible', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} onChange={mockOnChange} />);
      
      const page2 = screen.getByText('2');
      page2.focus();
      
      expect(page2).toHaveFocus();
      
      fireEvent.keyDown(page2, { key: 'Enter' });
      expect(mockOnChange).toHaveBeenCalledWith(2);
    });

    it('should navigate with arrow keys', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} current={3} onChange={mockOnChange} />);
      
      const pagination = screen.getByRole('navigation');
      
      fireEvent.keyDown(pagination, { key: 'ArrowRight' });
      expect(mockOnChange).toHaveBeenCalledWith(4);
      
      fireEvent.keyDown(pagination, { key: 'ArrowLeft' });
      expect(mockOnChange).toHaveBeenCalledWith(2);
    });
  });

  describe('Simple Mode', () => {
    it('should render simple pagination', () => {
      render(<Pagination total={100} simple />);
      
      // Should not show individual page numbers
      expect(screen.queryByText('2')).not.toBeInTheDocument();
      expect(screen.queryByText('3')).not.toBeInTheDocument();
    });

    it('should show current page in simple mode', () => {
      render(<Pagination total={100} current={5} pageSize={10} simple />);
      expect(screen.getByText('5 / 10')).toBeInTheDocument();
    });
  });

  describe('Jump to Page', () => {
    it('should show quick jumper when showQuickJumper is true', () => {
      render(<Pagination total={100} showQuickJumper />);
      const input = screen.getByPlaceholderText(/go to/i);
      expect(input).toBeInTheDocument();
    });

    it('should jump to page on Enter', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} showQuickJumper onChange={mockOnChange} />);
      
      const input = screen.getByPlaceholderText(/go to/i);
      fireEvent.change(input, { target: { value: '7' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      
      expect(mockOnChange).toHaveBeenCalledWith(7);
    });

    it('should validate jump input', () => {
      const mockOnChange = jest.fn();
      render(<Pagination total={100} pageSize={10} showQuickJumper onChange={mockOnChange} />);
      
      const input = screen.getByPlaceholderText(/go to/i);
      fireEvent.change(input, { target: { value: '999' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      
      // Should not jump to invalid page
      expect(mockOnChange).not.toHaveBeenCalledWith(999);
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<Pagination total={100} className="custom-pagination" />);
      const pagination = container.querySelector('.pagination');
      expect(pagination).toHaveClass('custom-pagination');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Pagination total={100} style={{ margin: '20px' }} />
      );
      const pagination = container.querySelector('.pagination');
      expect(pagination).toHaveStyle({ margin: '20px' });
    });
  });

  describe('Controlled Mode', () => {
    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Pagination total={100} current={1} onChange={mockOnChange} />
      );
      
      const page1 = screen.getByText('1');
      expect(page1.parentElement).toHaveClass('active');
      
      const page3 = screen.getByText('3');
      fireEvent.click(page3);
      
      expect(mockOnChange).toHaveBeenCalledWith(3);
      
      rerender(<Pagination total={100} current={3} onChange={mockOnChange} />);
      
      expect(page3.parentElement).toHaveClass('active');
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero total', () => {
      render(<Pagination total={0} />);
      const pagination = screen.getByRole('navigation');
      expect(pagination).toBeInTheDocument();
    });

    it('should handle single page', () => {
      render(<Pagination total={5} pageSize={10} />);
      
      const prevButton = screen.getByRole('button', { name: /previous/i });
      const nextButton = screen.getByRole('button', { name: /next/i });
      
      expect(prevButton).toBeDisabled();
      expect(nextButton).toBeDisabled();
    });

    it('should handle page size larger than total', () => {
      render(<Pagination total={5} pageSize={100} />);
      
      // Should only show 1 page
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.queryByText('2')).not.toBeInTheDocument();
    });
  });
});
