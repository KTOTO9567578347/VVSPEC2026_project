export default async function setup() {
  // Keep Vite in this process so Windows test teardown does not need taskkill.
  const { createServer, preview } = await import('vite');
  if (process.env.PLAYWRIGHT_BUILD === '1') {
    const server = await preview({ preview: { host: '127.0.0.1', port: 4175, strictPort: true } });
    return async () => {
      await new Promise<void>((resolve, reject) =>
        server.httpServer.close((error) => (error ? reject(error) : resolve())),
      );
    };
  }
  const server = await createServer({
    server: { host: '127.0.0.1', port: 4175, strictPort: true },
  });
  await server.listen();
  return async () => {
    await server.close();
  };
}
