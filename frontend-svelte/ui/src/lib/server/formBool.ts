/**
 * A checkbox paired with a hidden "false" field before it: the last value
 * wins ("true" when checked). Undefined when the form has no such field.
 */
export function formBool(data: FormData, name: string): boolean | undefined {
	const values = data.getAll(name);
	return values.length ? values.at(-1) === 'true' : undefined;
}
