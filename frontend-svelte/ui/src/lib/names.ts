/**
 * A comma-separated list of names (notable interpreters) as a clean list:
 * trimmed, without blanks or repeats (models sometimes loop over a list).
 */
export function splitNames(text: string): string[] {
	const seen = new Set<string>();
	const names: string[] = [];
	for (const raw of text.split(/[,;\n]/)) {
		const name = raw.trim().replace(/\.$/, '');
		const key = name.toLocaleLowerCase();
		if (name && !seen.has(key)) {
			seen.add(key);
			names.push(name);
		}
	}
	return names;
}
