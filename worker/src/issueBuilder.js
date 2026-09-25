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

export function isValidType(type) {
  return Object.prototype.hasOwnProperty.call(TYPE_LABELS, type);
}

export function isValidSeverity(severity) {
  return Object.prototype.hasOwnProperty.call(SEVERITY_LABELS, severity);
}

function fence(text) {
  const backtickRuns = text.match(/`+/g) || [];
  const longestRun = backtickRuns.reduce((max, run) => Math.max(max, run.length), 0);
  const marker = '`'.repeat(Math.max(3, longestRun + 1));
  return marker + '\n' + text + '\n' + marker;
}

function sanitizeVersion(value) {
  return (value || '').replace(/[^\w.\- ]/g, '');
}

export function buildIssuePayload(fields) {
  const type = isValidType(fields.type) ? fields.type : 'other';
  const rawSeverity = fields.type === 'bug' ? fields.severity : '';
  const severity = isValidSeverity(rawSeverity) ? rawSeverity : '';
  const description = (fields.description || '').trim();
  const truncated = description.slice(0, 60);

  const titlePrefix = severity
    ? `[${TYPE_TITLES[type]}][${severity}]`
    : `[${TYPE_TITLES[type]}]`;
  const title = `${titlePrefix} ${truncated}`;

  const labels = [TYPE_LABELS[type]];
  if (severity) {
    labels.push(SEVERITY_LABELS[severity]);
  }

  const lines = [`**Type:** ${TYPE_TITLES[type]}`];
  if (severity) {
    lines.push(`**Severity:** ${severity}`);
  }
  if (fields.blenderVersion) {
    lines.push(`**Blender version:** ${sanitizeVersion(fields.blenderVersion)}`);
  }
  if (fields.addonVersion) {
    lines.push(`**BlenderShelf version:** ${sanitizeVersion(fields.addonVersion)}`);
  }
  lines.push('', '**Description:**', fence(description));
  if (fields.contact) {
    lines.push('', '**Contact:**', fence(fields.contact));
  }
  lines.push('', '_Submitted via the website feedback form._');

  return { title, labels, body: lines.join('\n') };
}
