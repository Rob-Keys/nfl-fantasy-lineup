// Same-origin browser endpoint. The backend URL and shared secret are kept in
// Cloudflare Pages Function environment variables, never in the frontend.

const MAX_BODY_BYTES = 128 * 1024;
const MAX_RESPONSE_BYTES = 256 * 1024;

function json(body, status = 200) {
  return Response.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store' }
  });
}

export async function onRequestPost(context) {
  const { BACKEND_API_URL, BACKEND_SHARED_SECRET } = context.env;
  if (!BACKEND_API_URL || !BACKEND_SHARED_SECRET) {
    return json({ error: 'Backend proxy is not configured' }, 500);
  }

  const contentType = context.request.headers.get('content-type') || '';
  if (!contentType.toLowerCase().startsWith('application/json')) {
    return json({ error: 'Content-Type must be application/json' }, 415);
  }

  const body = await context.request.text();
  if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) {
    return json({ error: 'Request body is too large' }, 413);
  }

  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return json({ error: 'Request body must be valid JSON' }, 400);
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return json({ error: 'Request body must be a JSON object' }, 400);
  }

  let upstream;
  try {
    upstream = await fetch(BACKEND_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Api-Key': BACKEND_SHARED_SECRET
      },
      body: JSON.stringify(parsed)
    });
  } catch {
    return json({ error: 'Backend request failed' }, 502);
  }

  const contentLength = Number(upstream.headers.get('Content-Length') || 0);
  if (contentLength > MAX_RESPONSE_BYTES) {
    return json({ error: 'Backend response is too large' }, 502);
  }

  const responseBody = await upstream.arrayBuffer();
  if (responseBody.byteLength > MAX_RESPONSE_BYTES) {
    return json({ error: 'Backend response is too large' }, 502);
  }

  return new Response(responseBody, {
    status: upstream.status,
    headers: {
      'Content-Type': upstream.headers.get('Content-Type') || 'application/json',
      'Cache-Control': 'no-store'
    }
  });
}
