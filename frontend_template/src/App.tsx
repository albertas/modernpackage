import { useEffect, useState } from 'react';

type AppHealth = 'checking' | 'healthy' | 'unhealthy' | 'unavailable';
type DbHealth = 'checking' | 'ready' | 'not ready' | 'unavailable';

async function fetchStatus(path: string): Promise<'pass' | 'fail' | 'unavailable'> {
  try {
    const response = await fetch(path);
    const body = (await response.json()) as { status?: string };
    if (response.ok && body.status === 'pass') {
      return 'pass';
    }
    return 'fail';
  } catch {
    return 'unavailable';
  }
}

export function App() {
  const [appHealth, setAppHealth] = useState<AppHealth>('checking');
  const [dbHealth, setDbHealth] = useState<DbHealth>('checking');

  useEffect(() => {
    void fetchStatus('/livez').then((result) => {
      setAppHealth(
        result === 'pass' ? 'healthy' : result === 'fail' ? 'unhealthy' : 'unavailable',
      );
    });
    void fetchStatus('/readyz').then((result) => {
      setDbHealth(
        result === 'pass' ? 'ready' : result === 'fail' ? 'not ready' : 'unavailable',
      );
    });
  }, []);

  return (
    <main>
      <h1>modernpackage</h1>
      <dl>
        <dt>Application</dt>
        <dd>{appHealth}</dd>
        <dt>Database</dt>
        <dd>{dbHealth}</dd>
      </dl>
    </main>
  );
}
