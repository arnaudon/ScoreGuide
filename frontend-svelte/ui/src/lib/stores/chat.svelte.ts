type HistoryMessage = {
	question: string;
	[key: string]: unknown;
};

function createHistoryStore() {
	let history = $state<HistoryMessage[]>([]);
	let rawHistory = $state<unknown[]>([]);

	return {
		get history() {
			return history;
		},
		set history(value: HistoryMessage[]) {
			history = value;
		},

		get rawHistory() {
			return rawHistory;
		},
		set rawHistory(value: unknown[]) {
			rawHistory = value;
		},

		clear() {
			history = [];
			rawHistory = [];
		}
	};
}

export const mainAgentHistoryStore = createHistoryStore();
export const imslpAgentHistoryStore = createHistoryStore();
