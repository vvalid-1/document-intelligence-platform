// Phase 0 placeholder — replaced by Next.js in Phase 4
const http = require('http');

const HTML = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Document Intelligence Platform</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:80px auto;text-align:center">
  <h1>Document Intelligence Platform</h1>
  <p>Frontend placeholder &mdash; Phase 0</p>
  <p>Backend API: <a href="/api/docs">/api/docs</a></p>
</body>
</html>`;

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'frontend-placeholder' }));
    return;
  }
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(HTML);
});

server.listen(3000, '0.0.0.0', () => {
  console.log('Frontend placeholder listening on :3000');
});
