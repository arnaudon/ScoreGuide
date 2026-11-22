/** One CSV cell: quoted when needed, and never read as a formula by spreadsheets. */
export function csvCell(value: unknown): string {
	let text = value === null || value === undefined ? '' : String(value);
	if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
	return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}
