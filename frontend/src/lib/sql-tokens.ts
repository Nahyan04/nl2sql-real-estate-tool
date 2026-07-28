export type TokenKind = "keyword" | "function" | "string" | "number" | "comment" | "plain";

export interface SqlToken {
  text: string;
  kind: TokenKind;
}

const KEYWORDS =
  "SELECT|FROM|WHERE|GROUP\\s+BY|ORDER\\s+BY|HAVING|LIMIT|OFFSET|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|ON|AS|AND|OR|NOT|IN|IS|NULL|BETWEEN|LIKE|ILIKE|CASE|WHEN|THEN|ELSE|END|DISTINCT|UNION|ALL|WITH|ASC|DESC|INTERVAL|OVER|PARTITION|FILTER";

const FUNCTIONS =
  "SUM|COUNT|AVG|MIN|MAX|ROUND|COALESCE|DATE_TRUNC|EXTRACT|NOW|CURRENT_DATE|CAST|ABS|NULLIF|GREATEST|LEAST|TO_CHAR|LAG|LEAD|RANK|ROW_NUMBER";

// Order matters: comments and strings win over anything they contain.
const TOKEN = new RegExp(
  [
    `(--[^\\n]*|/\\*[\\s\\S]*?\\*/)`,
    `('(?:[^']|'')*')`,
    `\\b(${FUNCTIONS})\\b(?=\\s*\\()`,
    `\\b(${KEYWORDS})\\b`,
    `\\b(\\d+(?:\\.\\d+)?)\\b`,
  ].join("|"),
  "gi",
);

const KINDS: TokenKind[] = ["comment", "string", "function", "keyword", "number"];

/** The grammar here is only ever our own generated SQL, so a token pass beats
 *  pulling a highlighter whose theme would fight the palette. */
export function tokenizeSql(sql: string): SqlToken[] {
  const tokens: SqlToken[] = [];
  let cursor = 0;

  for (const match of sql.matchAll(TOKEN)) {
    const index = match.index ?? 0;
    if (index > cursor) tokens.push({ text: sql.slice(cursor, index), kind: "plain" });

    const group = match.slice(1).findIndex((value) => value !== undefined);
    tokens.push({ text: match[0], kind: KINDS[group] ?? "plain" });
    cursor = index + match[0].length;
  }

  if (cursor < sql.length) tokens.push({ text: sql.slice(cursor), kind: "plain" });
  return tokens;
}
