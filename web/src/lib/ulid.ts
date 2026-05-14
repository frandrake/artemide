// Lightweight client-side ULID for Idempotency-Key headers. Format is
// the same 26-character Crockford base32 layout as the server's ulid-py;
// uniqueness across two browser tabs in the same millisecond isn't a
// concern here.

const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

function encode(value: number, length: number): string {
  let out = '';
  for (let i = length - 1; i >= 0; i--) {
    const mod = value % 32;
    out = ALPHABET[mod] + out;
    value = Math.floor(value / 32);
  }
  return out;
}

export function generateUlid(): string {
  const ts = Date.now();
  const time = encode(ts, 10);
  const random = Array.from({ length: 16 }, () =>
    ALPHABET[Math.floor(Math.random() * 32)],
  ).join('');
  return time + random;
}
