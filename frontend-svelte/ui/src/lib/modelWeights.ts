/** "model = weight" lines to an object; null when a line is malformed. */
export function parseWeights(text: string): Record<string, number> | null {
	const weights: Record<string, number> = {};
	for (const line of text.split('\n')) {
		if (!line.trim()) continue;
		const at = line.lastIndexOf('=');
		const name = line.slice(0, at).trim();
		const weight = Number(line.slice(at + 1).trim());
		if (
			at < 1 ||
			!name ||
			line.slice(at + 1).trim() === '' ||
			!Number.isFinite(weight) ||
			weight < 0
		) {
			return null;
		}
		weights[name] = weight;
	}
	return weights;
}

/** The inverse of `parseWeights`, for the admin textarea. */
export function formatWeights(weights: Record<string, number>): string {
	return Object.entries(weights)
		.map(([name, weight]) => `${name} = ${weight}`)
		.join('\n');
}
