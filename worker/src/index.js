import { buildIssuePayload, isValidType, isValidSeverity } from './issueBuilder.js';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://blendershelf.github.io',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== 'POST') {
      return json(405, { ok: false, error: 'method not allowed' });
    }

    let fields;
    try {
      fields = await request.json();
    } catch (e) {
      return json(400, { ok: false, error: 'invalid JSON' });
    }
    if (!fields || typeof fields !== 'object') {
      return json(400, { ok: false, error: 'invalid payload' });
    }

    // Honeypot: a real visitor never fills this hidden field. Report success
    // without ever touching the GitHub API, so a bot's own success signal
    // tells it nothing changed and it has no reason to try a different field.
    if (fields.website) {
      return json(200, { ok: true });
    }

    // The client only offers the valid type/severity values, but this endpoint
    // is public and unauthenticated — anyone can POST to it directly, so the
    // server enforces the same allowlist rather than trusting the client.
    if (!isValidType(fields.type)) {
      return json(400, { ok: false, error: 'invalid type' });
    }
    if (fields.type === 'bug' && !isValidSeverity(fields.severity)) {
      return json(400, { ok: false, error: 'invalid severity' });
    }
    if (!fields.description || !String(fields.description).trim()) {
      return json(400, { ok: false, error: 'description required' });
    }

    const { title, labels, body } = buildIssuePayload(fields);

    const ghResponse = await fetch(
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/issues`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${env.GITHUB_ISSUE_TOKEN}`,
          Accept: 'application/vnd.github+json',
          'User-Agent': 'blendershelf-feedback-worker',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title, body, labels }),
      }
    );

    if (!ghResponse.ok) {
      return json(502, { ok: false, error: 'GitHub API error' });
    }

    return json(200, { ok: true });
  },
};
