/** Who makes a model, for people: the backend sends the Hugging Face org. */
const VENDORS: Record<string, string> = {
	moonshotai: 'Moonshot AI',
	mistralai: 'Mistral AI',
	qwen: 'Qwen (Alibaba)',
	google: 'Google',
	'swiss-ai': 'Swiss AI Initiative',
	'meta-llama': 'Meta',
	openai: 'OpenAI'
};

export function vendorName(vendor: string): string {
	return VENDORS[vendor.toLowerCase()] ?? vendor;
}
