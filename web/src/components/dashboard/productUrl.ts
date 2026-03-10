export function normalizeStoreBaseUrl(storeName: string) {
  const normalizedStore = storeName.trim().replace(/^https?:\/\//i, '').replace(/\/+$/, '');
  if (!normalizedStore) {
    return '';
  }

  return normalizedStore.includes('.')
    ? `https://${normalizedStore}`
    : `https://${normalizedStore}.myikas.com`;
}

export function slugifyProductName(name?: string | null) {
  const value = (name || '')
    .trim()
    .toLocaleLowerCase('tr-TR')
    .replace(/\u0131/g, 'i')
    .replace(/\u011f/g, 'g')
    .replace(/\u00fc/g, 'u')
    .replace(/\u015f/g, 's')
    .replace(/\u00f6/g, 'o')
    .replace(/\u00e7/g, 'c')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return value;
}

export function buildIkasProductUrl(
  storeName: string,
  slug?: string | null,
  productId?: string,
  productName?: string | null,
) {
  const baseUrl = normalizeStoreBaseUrl(storeName);
  if (!baseUrl) {
    return '';
  }

  const normalizedSlug = slug?.trim().replace(/^\/+/, '');
  if (normalizedSlug) {
    return `${baseUrl}/${normalizedSlug}`;
  }

  const guessedSlug = slugifyProductName(productName);
  if (guessedSlug) {
    return `${baseUrl}/${guessedSlug}`;
  }

  const normalizedProductId = productId?.trim();
  if (!normalizedProductId) {
    return '';
  }

  return `${baseUrl}/product/edit/${normalizedProductId}`;
}
