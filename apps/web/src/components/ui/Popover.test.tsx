/**
 * Unit tests for Popover component
 * 
 * Tests popover functionality including:
 * - Rendering and display
 * - Open/close states
 * - Positioning
 * - Triggers (click, hover, focus)
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Popover, PopoverTrigger, PopoverContent } from './Popover';

describe('Popover Component', () => {
  describe('Rendering', () => {
    it('should render popover trigger', () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      expect(screen.getByText('Open Popover')).toBeInTheDocument();
    });

    it('should not render content by default', () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
    });

    it('should render with title', () => {
      render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent title="Popover Title">
            Popover content
          </PopoverContent>
        </Popover>
      );
      
      expect(screen.getByText('Popover Title')).toBeInTheDocument();
    });
  });

  describe('Open/Close Behavior', () => {
    it('should open on click by default', async () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
    });

    it('should close on second click', async () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      
      fireEvent.click(trigger);
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
      
      fireEvent.click(trigger);
      await waitFor(() => {
        expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      });
    });

    it('should close on outside click', async () => {
      render(
        <div>
          <Popover>
            <PopoverTrigger>
              <button>Open Popover</button>
            </PopoverTrigger>
            <PopoverContent>Popover content</PopoverContent>
          </Popover>
          <div data-testid="outside">Outside element</div>
        </div>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
      
      const outside = screen.getByTestId('outside');
      fireEvent.mouseDown(outside);
      
      await waitFor(() => {
        expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      });
    });

    it('should close on Escape key', async () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
      
      fireEvent.keyDown(document, { key: 'Escape' });
      
      await waitFor(() => {
        expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      });
    });
  });

  describe('Trigger Types', () => {
    it('should open on hover when trigger is hover', async () => {
      render(
        <Popover trigger="hover">
          <PopoverTrigger>
            <button>Hover me</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Hover me');
      fireEvent.mouseEnter(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
    });

    it('should close on mouse leave when trigger is hover', async () => {
      render(
        <Popover trigger="hover">
          <PopoverTrigger>
            <button>Hover me</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Hover me');
      fireEvent.mouseEnter(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
      
      fireEvent.mouseLeave(trigger);
      
      await waitFor(() => {
        expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      });
    });

    it('should open on focus when trigger is focus', async () => {
      render(
        <Popover trigger="focus">
          <PopoverTrigger>
            <button>Focus me</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Focus me');
      trigger.focus();
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
    });
  });

  describe('Positioning', () => {
    it('should position at top by default', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveAttribute('data-placement', 'top');
    });

    it('should position at bottom', () => {
      const { container } = render(
        <Popover defaultOpen placement="bottom">
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveAttribute('data-placement', 'bottom');
    });

    it('should position at left', () => {
      const { container } = render(
        <Popover defaultOpen placement="left">
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveAttribute('data-placement', 'left');
    });

    it('should position at right', () => {
      const { container } = render(
        <Popover defaultOpen placement="right">
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveAttribute('data-placement', 'right');
    });
  });

  describe('Controlled Mode', () => {
    it('should work in controlled mode', async () => {
      const mockOnOpenChange = jest.fn();
      const { rerender } = render(
        <Popover isOpen={false} onOpenChange={mockOnOpenChange}>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      expect(mockOnOpenChange).toHaveBeenCalledWith(true);
      
      rerender(
        <Popover isOpen={true} onOpenChange={mockOnOpenChange}>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      expect(screen.getByText('Popover content')).toBeInTheDocument();
    });
  });

  describe('Arrow', () => {
    it('should render arrow by default', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const arrow = container.querySelector('.popover-arrow');
      expect(arrow).toBeInTheDocument();
    });

    it('should not render arrow when showArrow is false', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent showArrow={false}>Popover content</PopoverContent>
        </Popover>
      );
      
      const arrow = container.querySelector('.popover-arrow');
      expect(arrow).not.toBeInTheDocument();
    });
  });

  describe('Close Button', () => {
    it('should render close button when showCloseButton is true', () => {
      render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent showCloseButton>Popover content</PopoverContent>
        </Popover>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });

    it('should close popover when close button is clicked', async () => {
      render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent showCloseButton>Popover content</PopoverContent>
        </Popover>
      );
      
      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);
      
      await waitFor(() => {
        expect(screen.queryByText('Popover content')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      expect(trigger).toHaveAttribute('aria-haspopup', 'dialog');
      expect(trigger).toHaveAttribute('aria-expanded', 'false');
    });

    it('should update aria-expanded when opened', async () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        expect(trigger).toHaveAttribute('aria-expanded', 'true');
      });
    });

    it('should have role="dialog" on content', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const content = container.querySelector('[role="dialog"]');
      expect(content).toBeInTheDocument();
    });

    it('should have aria-labelledby when title is provided', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent title="Popover Title">
            Popover content
          </PopoverContent>
        </Popover>
      );
      
      const content = container.querySelector('[role="dialog"]');
      expect(content).toHaveAttribute('aria-labelledby');
    });

    it('should trap focus when open', async () => {
      render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent showCloseButton>
            <button>Button inside</button>
            Popover content
          </PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        expect(screen.getByText('Popover content')).toBeInTheDocument();
      });
      
      const insideButton = screen.getByText('Button inside');
      expect(document.activeElement).toBe(insideButton);
    });
  });

  describe('Animation', () => {
    it('should animate entrance', async () => {
      const { container } = render(
        <Popover>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        const popover = container.querySelector('.popover-content');
        expect(popover).toHaveClass('entering');
      });
    });

    it('should animate exit', async () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const trigger = screen.getByText('Open Popover');
      fireEvent.click(trigger);
      
      await waitFor(() => {
        const popover = container.querySelector('.popover-content');
        expect(popover).toHaveClass('exiting');
      });
    });
  });

  describe('Offset', () => {
    it('should apply offset', () => {
      const { container } = render(
        <Popover defaultOpen offset={20}>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveStyle({ '--popover-offset': '20px' });
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent className="custom-popover">
            Popover content
          </PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveClass('custom-popover');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Popover defaultOpen>
          <PopoverTrigger>
            <button>Open Popover</button>
          </PopoverTrigger>
          <PopoverContent style={{ backgroundColor: 'red' }}>
            Popover content
          </PopoverContent>
        </Popover>
      );
      
      const popover = container.querySelector('.popover-content');
      expect(popover).toHaveStyle({ backgroundColor: 'red' });
    });
  });
});
