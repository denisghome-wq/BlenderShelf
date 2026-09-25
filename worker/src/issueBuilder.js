const TYPE_LABELS = {
  bug: 'type:bug',
  feature: 'type:feature',
  question: 'type:question',
  other: 'type:other',
};

const TYPE_TITLES = {
  bug: 'Bug',
  feature: 'Feature',
  question: 'Question',
  other: 'Other',
};

const SEVERITY_LABELS = {
  critical: 'severity:critical',
  major: 'severity:major',
  minor: 'severity:minor',
};

function fence(text) {
  return '```\n' + text + '\n```';
}

export function buildIssuePayload(fields) {
  const type = fields.type || 'other';
  const severity = fields.type === 'bug' ? fields.severity : '';
  const description = (fields.description || '').trim();
  const truncated = description.slice(0, 60);

  const titlePrefix = severity
    ? `[${TYPE_TITLES[type]}][${severity}]`
    : `[${TYPE_TITLES[type]}]`;
  const title = `${titlePrefix} ${truncated}`;

  const labels = [TYPE_LABELS[type]];
  if (severity && SEVERITY_LABELS[severity]) {
    labels.push(SEVERITY_LABELS[severity]);
  }

  const lines = [`**Type:** ${TYPE_TITLES[type]}`];
  if (severity) {
    lines.push(`**Severity:** ${severity}`);
  }
  if (fields.blenderVersion) {
    lines.push(`**Blender version:** ${fields.blenderVersion}`);
  }
  if (fields.addonVersion) {
    lines.push(`**BlenderShelf version:** ${fields.addonVersion}`);
  }
  lines.push('', '**Description:**', fence(description));
  if (fields.contact) {
    lines.push('', '**Contact:**', fence(fields.contact));
  }
  lines.push('', '_Submitted via the website feedback form._');

  return { title, labels, body: lines.join('\n') };
}
