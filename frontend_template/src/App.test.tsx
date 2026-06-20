import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

function mockFetch(impl: (path: string) => Promise<Response>) {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) =>
    impl(String(input)),
  ) as typeof fetch;
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('App', () => {
  it('renders the heading', () => {
    mockFetch(() => Promise.resolve(jsonResponse(200, { status: 'pass' })));
    render(<App />);
    expect(screen.getByRole('heading', { name: 'modernpackage' })).toBeInTheDocument();
  });

  it('shows healthy and ready when both endpoints pass', async () => {
    mockFetch(() => Promise.resolve(jsonResponse(200, { status: 'pass' })));
    render(<App />);
    expect(await screen.findByText('healthy')).toBeInTheDocument();
    expect(await screen.findByText('ready')).toBeInTheDocument();
  });

  it('shows unhealthy and not ready when endpoints fail', async () => {
    mockFetch((path) =>
      Promise.resolve(
        path.includes('readyz')
          ? jsonResponse(503, { status: 'fail' })
          : jsonResponse(500, { status: 'fail' }),
      ),
    );
    render(<App />);
    expect(await screen.findByText('unhealthy')).toBeInTheDocument();
    expect(await screen.findByText('not ready')).toBeInTheDocument();
  });

  it('shows unavailable when fetch rejects', async () => {
    mockFetch(() => Promise.reject(new Error('network down')));
    render(<App />);
    const unavailable = await screen.findAllByText('unavailable');
    expect(unavailable).toHaveLength(2);
  });
});
