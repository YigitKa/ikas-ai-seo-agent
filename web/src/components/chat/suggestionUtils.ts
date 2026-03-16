// ── Types ─────────────────────────────────────────────────────────────────────

export interface SuggestionOption {
  tone: string;
  value: string;
  action?: string;
}

// ── Parsing ───────────────────────────────────────────────────────────────────

function normalizeSuggestionValue(value: string): string {
  let normalized = value.trim().replace(/\r\n/g, '\n').replace(/\\n/g, '\n');

  const hasWrappingDoubleQuotes =
    normalized.length > 1 && normalized.startsWith('"') && normalized.endsWith('"');
  const hasWrappingSingleQuotes =
    normalized.length > 1 && normalized.startsWith("'") && normalized.endsWith("'");

  if (hasWrappingDoubleQuotes || hasWrappingSingleQuotes) {
    normalized = normalized.slice(1, -1).trim();
  }

  return normalized;
}

function parseStructuredOptions(value: string): SuggestionOption[] {
  try {
    return parseSuggestionOptions(JSON.parse(value));
  } catch {
    return [];
  }
}

export function parseSuggestionOptions(rawValue: unknown): SuggestionOption[] {
  if (!Array.isArray(rawValue)) {
    return [];
  }

  return rawValue.reduce<SuggestionOption[]>((items, entry) => {
    if (!entry || typeof entry !== 'object') {
      return items;
    }

    const candidate = entry as { tone?: unknown; value?: unknown; action?: unknown };
    const tone = typeof candidate.tone === 'string' ? candidate.tone.trim() : '';
    const value = typeof candidate.value === 'string' ? normalizeSuggestionValue(candidate.value) : '';
    const action = typeof candidate.action === 'string' ? candidate.action.trim() : '';
    if (!tone || !value) {
      return items;
    }

    items.push(action ? { tone, value, action } : { tone, value });
    return items;
  }, []);
}

function removeRanges(text: string, ranges: { start: number; end: number }[]) {
  if (!ranges.length) return text;
  const sorted = [...ranges].sort((a, b) => b.start - a.start);
  let result = text;
  for (const range of sorted) {
    result = `${result.slice(0, range.start)}${result.slice(range.end)}`;
  }
  return result;
}

export function extractSuggestionOptions(content: string) {
  const matcher = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  const matchedRanges: { start: number; end: number }[] = [];
  const parsedOptions: SuggestionOption[] = [];
  let match: RegExpExecArray | null;

  while ((match = matcher.exec(content)) !== null) {
    const options = parseStructuredOptions(match[1]);
    if (!options.length) continue;
    matchedRanges.push({ start: match.index, end: match.index + match[0].length });
    parsedOptions.push(...options);
  }

  if (!parsedOptions.length) {
    const trailingArrayMatch = content.match(/(\[[\s\S]*\])\s*$/);
    if (trailingArrayMatch?.[1]) {
      const options = parseStructuredOptions(trailingArrayMatch[1]);
      if (options.length) {
        const rawArray = trailingArrayMatch[1];
        const start = content.lastIndexOf(rawArray);
        if (start !== -1) matchedRanges.push({ start, end: start + rawArray.length });
        parsedOptions.push(...options);
      }
    }
  }

  let markdownContent = matchedRanges.length ? removeRanges(content, matchedRanges) : content;

  if (!matchedRanges.length) {
    const lowerContent = content.toLowerCase();
    const trailingJsonBlockIndex = lowerContent.lastIndexOf('```json');
    if (trailingJsonBlockIndex !== -1 && lowerContent.indexOf('```', trailingJsonBlockIndex + 7) === -1) {
      markdownContent = content.slice(0, trailingJsonBlockIndex);
    }
  }

  return {
    markdownContent: markdownContent.replace(/\n{3,}/g, '\n\n').trim(),
    options: parsedOptions,
  };
}

// ── Palette ───────────────────────────────────────────────────────────────────

type SuggestionPalette = {
  accent: string;
  background: string;
  border: string;
  badgeBackground: string;
  badgeColor: string;
  buttonBackground: string;
  buttonBorder: string;
  buttonColor: string;
  shadow: string;
};

const FALLBACK_PALETTES: SuggestionPalette[] = [
  {
    accent: '#a78bfa',
    background: 'linear-gradient(145deg, rgba(167, 139, 250, 0.12), rgba(15, 23, 42, 0.94))',
    border: 'rgba(167, 139, 250, 0.22)',
    badgeBackground: 'rgba(167, 139, 250, 0.14)',
    badgeColor: '#c4b5fd',
    buttonBackground: 'rgba(167, 139, 250, 0.12)',
    buttonBorder: 'rgba(167, 139, 250, 0.24)',
    buttonColor: '#ede9fe',
    shadow: '0 18px 34px rgba(167, 139, 250, 0.1)',
  },
  {
    accent: '#f59e0b',
    background: 'linear-gradient(145deg, rgba(245, 158, 11, 0.12), rgba(15, 23, 42, 0.94))',
    border: 'rgba(245, 158, 11, 0.22)',
    badgeBackground: 'rgba(245, 158, 11, 0.14)',
    badgeColor: '#fcd34d',
    buttonBackground: 'rgba(245, 158, 11, 0.12)',
    buttonBorder: 'rgba(245, 158, 11, 0.24)',
    buttonColor: '#fef3c7',
    shadow: '0 18px 34px rgba(245, 158, 11, 0.1)',
  },
  {
    accent: '#22c55e',
    background: 'linear-gradient(145deg, rgba(34, 197, 94, 0.12), rgba(15, 23, 42, 0.94))',
    border: 'rgba(34, 197, 94, 0.22)',
    badgeBackground: 'rgba(34, 197, 94, 0.14)',
    badgeColor: '#86efac',
    buttonBackground: 'rgba(34, 197, 94, 0.12)',
    buttonBorder: 'rgba(34, 197, 94, 0.24)',
    buttonColor: '#dcfce7',
    shadow: '0 18px 34px rgba(34, 197, 94, 0.1)',
  },
];

export function getSuggestionCardPalette(tone: string, index: number): SuggestionPalette {
  const normalizedTone = tone.toLocaleLowerCase('tr-TR');

  if (normalizedTone.includes('agresif') || normalizedTone.includes('iddiali')) {
    return {
      accent: '#f97316',
      background: 'linear-gradient(145deg, rgba(249, 115, 22, 0.14), rgba(15, 23, 42, 0.94))',
      border: 'rgba(249, 115, 22, 0.24)',
      badgeBackground: 'rgba(249, 115, 22, 0.14)',
      badgeColor: '#fdba74',
      buttonBackground: 'rgba(249, 115, 22, 0.12)',
      buttonBorder: 'rgba(249, 115, 22, 0.24)',
      buttonColor: '#ffedd5',
      shadow: '0 18px 34px rgba(249, 115, 22, 0.12)',
    };
  }

  if (normalizedTone.includes('guvenli') || normalizedTone.includes('temkinli')) {
    return {
      accent: '#10b981',
      background: 'linear-gradient(145deg, rgba(16, 185, 129, 0.12), rgba(15, 23, 42, 0.94))',
      border: 'rgba(16, 185, 129, 0.22)',
      badgeBackground: 'rgba(16, 185, 129, 0.14)',
      badgeColor: '#6ee7b7',
      buttonBackground: 'rgba(16, 185, 129, 0.12)',
      buttonBorder: 'rgba(16, 185, 129, 0.24)',
      buttonColor: '#d1fae5',
      shadow: '0 18px 34px rgba(16, 185, 129, 0.1)',
    };
  }

  if (normalizedTone.includes('teknik') || normalizedTone.includes('seo')) {
    return {
      accent: '#38bdf8',
      background: 'linear-gradient(145deg, rgba(56, 189, 248, 0.12), rgba(15, 23, 42, 0.94))',
      border: 'rgba(56, 189, 248, 0.22)',
      badgeBackground: 'rgba(56, 189, 248, 0.14)',
      badgeColor: '#7dd3fc',
      buttonBackground: 'rgba(56, 189, 248, 0.12)',
      buttonBorder: 'rgba(56, 189, 248, 0.24)',
      buttonColor: '#e0f2fe',
      shadow: '0 18px 34px rgba(56, 189, 248, 0.1)',
    };
  }

  return FALLBACK_PALETTES[index % FALLBACK_PALETTES.length];
}
