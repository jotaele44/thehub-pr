import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { Toaster } from '@/components/ui/toaster';
import { toast } from '@/components/ui/use-toast';

// The local Toast primitives are not Radix, so dismissal is driven by use-toast's
// own timer + the Toaster filtering closed toasts. Guard that behavior.
describe('Toaster', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    act(() => vi.runOnlyPendingTimers()); // flush pending dismiss/remove so state resets
    vi.useRealTimers();
  });

  it('auto-dismisses a toast after its duration', () => {
    render(<Toaster />);
    act(() => { toast({ title: 'Saved' }); });
    expect(screen.getByText('Saved')).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });

  it('dismisses when the close button is clicked', () => {
    render(<Toaster />);
    act(() => { toast({ title: 'Closable' }); });
    const closeButton = screen.getByRole('button');
    act(() => { fireEvent.click(closeButton); });
    expect(screen.queryByText('Closable')).not.toBeInTheDocument();
  });
});
