/**
 * Unit tests for FileUpload component
 * 
 * Tests file upload functionality including:
 * - Rendering and display
 * - File selection
 * - Drag and drop
 * - File validation
 * - Multiple files
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { FileUpload } from './FileUpload';

describe('FileUpload Component', () => {
  describe('Rendering', () => {
    it('should render file upload', () => {
      render(<FileUpload />);
      const input = screen.getByRole('button', { name: /upload/i });
      expect(input).toBeInTheDocument();
    });

    it('should render with label', () => {
      render(<FileUpload label="Upload Files" />);
      expect(screen.getByText('Upload Files')).toBeInTheDocument();
    });

    it('should render with description', () => {
      render(
        <FileUpload
          label="Upload Files"
          description="Drag and drop files here"
        />
      );
      
      expect(screen.getByText('Drag and drop files here')).toBeInTheDocument();
    });

    it('should render drop zone', () => {
      const { container } = render(<FileUpload />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      expect(dropZone).toBeInTheDocument();
    });
  });

  describe('File Selection', () => {
    it('should open file dialog on click', () => {
      render(<FileUpload />);
      const button = screen.getByRole('button', { name: /upload/i });
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const clickSpy = jest.spyOn(input, 'click');
      
      fireEvent.click(button);
      expect(clickSpy).toHaveBeenCalled();
    });

    it('should handle file selection', () => {
      const mockOnChange = jest.fn();
      render(<FileUpload onChange={mockOnChange} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      expect(mockOnChange).toHaveBeenCalled();
    });

    it('should display selected file', async () => {
      render(<FileUpload />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        expect(screen.getByText('test.txt')).toBeInTheDocument();
      });
    });
  });

  describe('Multiple Files', () => {
    it('should allow multiple file selection', () => {
      render(<FileUpload multiple />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toHaveAttribute('multiple');
    });

    it('should handle multiple files', () => {
      const mockOnChange = jest.fn();
      render(<FileUpload multiple onChange={mockOnChange} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const files = [
        new File(['content1'], 'test1.txt', { type: 'text/plain' }),
        new File(['content2'], 'test2.txt', { type: 'text/plain' })
      ];
      
      Object.defineProperty(input, 'files', {
        value: files,
        writable: false
      });
      
      fireEvent.change(input);
      
      expect(mockOnChange).toHaveBeenCalled();
    });

    it('should display multiple files', async () => {
      render(<FileUpload multiple />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const files = [
        new File(['content1'], 'test1.txt', { type: 'text/plain' }),
        new File(['content2'], 'test2.txt', { type: 'text/plain' })
      ];
      
      Object.defineProperty(input, 'files', {
        value: files,
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        expect(screen.getByText('test1.txt')).toBeInTheDocument();
        expect(screen.getByText('test2.txt')).toBeInTheDocument();
      });
    });
  });

  describe('Drag and Drop', () => {
    it('should handle drag enter', () => {
      const { container } = render(<FileUpload />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      
      fireEvent.dragEnter(dropZone!);
      
      expect(dropZone).toHaveClass('drag-over');
    });

    it('should handle drag leave', () => {
      const { container } = render(<FileUpload />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      
      fireEvent.dragEnter(dropZone!);
      expect(dropZone).toHaveClass('drag-over');
      
      fireEvent.dragLeave(dropZone!);
      expect(dropZone).not.toHaveClass('drag-over');
    });

    it('should handle file drop', () => {
      const mockOnChange = jest.fn();
      const { container } = render(<FileUpload onChange={mockOnChange} />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      const dataTransfer = {
        files: [file],
        items: [{ kind: 'file', type: 'text/plain', getAsFile: () => file }],
        types: ['Files']
      };
      
      fireEvent.drop(dropZone!, { dataTransfer });
      
      expect(mockOnChange).toHaveBeenCalled();
    });

    it('should prevent default drag over behavior', () => {
      const { container } = render(<FileUpload />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      
      const event = new Event('dragover', { bubbles: true, cancelable: true });
      const preventDefaultSpy = jest.spyOn(event, 'preventDefault');
      
      dropZone!.dispatchEvent(event);
      
      expect(preventDefaultSpy).toHaveBeenCalled();
    });
  });

  describe('File Validation', () => {
    it('should validate file type', () => {
      const mockOnError = jest.fn();
      render(<FileUpload accept=".txt" onError={mockOnError} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      expect(mockOnError).toHaveBeenCalledWith(expect.stringContaining('type'));
    });

    it('should validate file size', () => {
      const mockOnError = jest.fn();
      render(<FileUpload maxSize={1024} onError={mockOnError} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const largeContent = 'x'.repeat(2048);
      const file = new File([largeContent], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      expect(mockOnError).toHaveBeenCalledWith(expect.stringContaining('size'));
    });

    it('should validate max files', () => {
      const mockOnError = jest.fn();
      render(<FileUpload multiple maxFiles={2} onError={mockOnError} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const files = [
        new File(['content1'], 'test1.txt', { type: 'text/plain' }),
        new File(['content2'], 'test2.txt', { type: 'text/plain' }),
        new File(['content3'], 'test3.txt', { type: 'text/plain' })
      ];
      
      Object.defineProperty(input, 'files', {
        value: files,
        writable: false
      });
      
      fireEvent.change(input);
      
      expect(mockOnError).toHaveBeenCalledWith(expect.stringContaining('maximum'));
    });
  });

  describe('File Removal', () => {
    it('should show remove button for selected files', async () => {
      render(<FileUpload />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const removeButton = screen.getByRole('button', { name: /remove/i });
        expect(removeButton).toBeInTheDocument();
      });
    });

    it('should remove file on remove button click', async () => {
      const mockOnChange = jest.fn();
      render(<FileUpload onChange={mockOnChange} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const removeButton = screen.getByRole('button', { name: /remove/i });
        fireEvent.click(removeButton);
      });
      
      expect(screen.queryByText('test.txt')).not.toBeInTheDocument();
    });
  });

  describe('Disabled State', () => {
    it('should render disabled file upload', () => {
      render(<FileUpload disabled />);
      const button = screen.getByRole('button', { name: /upload/i });
      expect(button).toBeDisabled();
    });

    it('should not accept files when disabled', () => {
      const mockOnChange = jest.fn();
      render(<FileUpload disabled onChange={mockOnChange} />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeDisabled();
    });

    it('should not accept drag and drop when disabled', () => {
      const mockOnChange = jest.fn();
      const { container } = render(<FileUpload disabled onChange={mockOnChange} />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      const dataTransfer = { files: [file] };
      
      fireEvent.drop(dropZone!, { dataTransfer });
      
      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  describe('Preview', () => {
    it('should show image preview for image files', async () => {
      render(<FileUpload showPreview />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.png', { type: 'image/png' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const preview = screen.getByRole('img');
        expect(preview).toBeInTheDocument();
      });
    });

    it('should show file icon for non-image files', async () => {
      render(<FileUpload showPreview />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const icon = screen.getByTestId('file-icon');
        expect(icon).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(<FileUpload label="Upload Files" />);
      const button = screen.getByRole('button', { name: /upload/i });
      expect(button).toHaveAttribute('aria-label');
    });

    it('should have aria-disabled when disabled', () => {
      render(<FileUpload disabled />);
      const button = screen.getByRole('button', { name: /upload/i });
      expect(button).toHaveAttribute('aria-disabled', 'true');
    });

    it('should be keyboard accessible', () => {
      render(<FileUpload />);
      const button = screen.getByRole('button', { name: /upload/i });
      
      button.focus();
      expect(button).toHaveFocus();
      
      fireEvent.keyDown(button, { key: 'Enter' });
      // Should trigger file dialog
    });

    it('should announce file selection to screen readers', async () => {
      render(<FileUpload />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const announcement = screen.getByRole('status');
        expect(announcement).toHaveTextContent(/selected/i);
      });
    });
  });

  describe('Error State', () => {
    it('should render with error state', () => {
      const { container } = render(<FileUpload error />);
      const wrapper = container.querySelector('.file-upload-wrapper');
      expect(wrapper).toHaveClass('error');
    });

    it('should render with error message', () => {
      render(<FileUpload error errorMessage="Upload failed" />);
      expect(screen.getByText('Upload failed')).toBeInTheDocument();
    });

    it('should have aria-invalid when error', () => {
      const { container } = render(<FileUpload error />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      expect(dropZone).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Required State', () => {
    it('should render required indicator', () => {
      render(<FileUpload label="Upload Files" required />);
      const required = screen.getByText('*');
      expect(required).toBeInTheDocument();
    });

    it('should have aria-required when required', () => {
      const { container } = render(<FileUpload required />);
      const dropZone = container.querySelector('.file-upload-dropzone');
      expect(dropZone).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Upload Progress', () => {
    it('should show progress bar during upload', async () => {
      render(<FileUpload showProgress />);
      
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false
      });
      
      fireEvent.change(input);
      
      await waitFor(() => {
        const progress = screen.getByRole('progressbar');
        expect(progress).toBeInTheDocument();
      });
    });

    it('should update progress value', async () => {
      render(<FileUpload showProgress uploadProgress={50} />);
      
      const progress = screen.getByRole('progressbar');
      expect(progress).toHaveAttribute('aria-valuenow', '50');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(<FileUpload className="custom-upload" />);
      const wrapper = container.querySelector('.file-upload-wrapper');
      expect(wrapper).toHaveClass('custom-upload');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <FileUpload style={{ margin: '20px' }} />
      );
      const wrapper = container.querySelector('.file-upload-wrapper');
      expect(wrapper).toHaveStyle({ margin: '20px' });
    });
  });
});
