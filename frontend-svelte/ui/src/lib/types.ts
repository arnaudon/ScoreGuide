/**
 * TypeScript mirrors of the Python response/table models in `shared/shared/`.
 * Hand-maintained subset covering what the Svelte app actually consumes; if
 * the backend schema diverges, update both sides together.
 */

export type Difficulty = 'easy' | 'moderate' | 'intermediate' | 'advanced' | 'expert';

export type Period =
	'Medieval' | 'Renaissance' | 'Baroque' | 'Classical' | 'Romantic' | 'Modernist' | 'Postmodernist';

/** Matches `shared.scores.Score`. */
export interface Score {
	id: number;
	title: string;
	composer: string;
	year: number;
	period: Period;
	genre: string;
	form: string;
	style: string;
	key: string;
	instrumentation: string;
	pdf_path: string;
	/** Bytes of the stored PDF (0 when unknown); counts against the storage limit. */
	pdf_size?: number;
	number_of_plays: number;
	/** When the score was last opened in the reader (naive UTC), null if never. */
	last_played_at?: string | null;
	source: string;
	imslp_id: number | null;
	user_id: number | null;
	short_description: string;
	short_description_fr: string;
	long_description: string;
	long_description_fr: string;
	youtube_url: string;
	difficulty: Difficulty;
	notable_interpreters: string;
}

/** Matches `shared.scores.ScoreSection`: one table-of-contents entry. */
export interface ScoreSection {
	id: number;
	score_id: number;
	position: number;
	title: string;
	page: number;
	source: string;
	incipit_path: string;
	version: number;
	/** 0: a piece (or an entry of a flat list), 1: a movement of the piece above. */
	level: number;
}

/** Matches `app.sections.SectionsResponse`. */
export interface SectionsResponse {
	status: 'ready' | 'running' | 'error' | 'none';
	sections: ScoreSection[];
	confidence: 'high' | 'medium' | 'low' | null;
	/** Detector version of the stored entries (null without sections). */
	version: number | null;
	latest_version: number;
}

/** Matches `shared.scores.IMSLP`. */
export interface IMSLPScore {
	id: number;
	/** IMSLP page id (null on rows from the old scraper). */
	pageid: number | null;
	title: string;
	composer: string;
	/** "Op.38", "BWV 988". */
	catalogue: string;
	/** 0 when unknown. */
	year: number;
	period: string | null;
	genre: string;
	form: string;
	style: string;
	key: string;
	instrumentation: string;
	permlink: string;
	score_metadata: string;
	pdf_urls: string;
}

/** Matches `app.imslp.ImslpResult`: a catalogue search hit. */
export type ImslpResult = Pick<
	IMSLPScore,
	| 'id'
	| 'title'
	| 'composer'
	| 'catalogue'
	| 'year'
	| 'period'
	| 'genre'
	| 'key'
	| 'instrumentation'
	| 'permlink'
> & { in_library: boolean };

/** Matches `app.imslp.ImslpFile`: one score file and its IMSLP page. */
export interface ImslpFile {
	file: string;
	description: string;
	copyright: string;
	url: string;
}

/** Matches `app.imslp.ImslpSearch`. */
export interface ImslpSearch {
	total: number;
	results: ImslpResult[];
}

/** Matches `shared.user.User` (subset exposed via `/user`). Password is never returned. */
export interface User {
	id: number;
	username: string;
	email: string | null;
	first_name: string | null;
	last_name: string | null;
	instrument: string | null;
	role: string;
	/** Billing plan: "free" or "pro". */
	plan: string;
	last_login: string | null;
	/** False until the emailed confirmation link is opened (when verification is on). */
	email_verified?: boolean;
	/** Plan limits and use so far (only from `GET /user`). */
	usage?: UsageSummary | null;
}

/** Matches `shared.usage.UsageSummary`. Storage in bytes; AI in weighted tokens used of all received. */
export interface UsageSummary {
	plan: string;
	ai_used: number;
	ai_allowance: number;
	storage_used: number;
	storage_limit: number;
}

/** Admin `/users` includes the score count and the user's limit overrides. */
export interface AdminUser extends User {
	score_count: number;
	ai_allowance: number | null;
	storage_limit_mb: number | null;
}

/** Matches `app.plans.PlanLimits`. */
export interface PlanLimits {
	ai_tokens: number;
	storage_mb: number;
}

/** Matches `app.plans.PlanSettings`. */
export interface PlanSettings {
	limits: Record<'free' | 'pro', PlanLimits>;
	weights: Record<string, number>;
}

/** Matches `app.plans.UsageRow`: one user's month, the billing export. */
export interface UsageRow {
	user_id: number;
	username: string;
	email: string | null;
	plan: string;
	requests: number;
	input_tokens: number;
	output_tokens: number;
	cost: number;
	/** Tokens an admin added to the account that month. */
	granted: number;
	/** Totals so far (not just that month): tokens used and received. */
	ai_used: number;
	ai_allowance: number;
	storage_used: number;
	storage_limit: number;
}

/** Matches `shared.responses.Response`. */
export interface AgentResponse {
	response: string;
	score_id?: number | null;
	score_ids?: number[] | null;
}

/** Matches `shared.responses.ImslpResponse`. */
export interface ImslpAgentResponse {
	response: string;
	score_ids: number[];
}

/** Wire shape of `FullResponse` / `ImslpFullResponse`. */
export interface FullAgentResponse<T = AgentResponse> {
	response: T;
	message_history: unknown[];
}

export interface ImslpStats {
	total_works: number;
	total_composers: number;
}

/** Matches `app.imslp` sync state (`POST /imslp/progress`). */
export interface ImslpProgress {
	status: 'idle' | 'running' | 'cancelled' | 'completed' | 'error';
	/** Position in IMSLP's alphabetical work list. */
	start: number;
	/** Works stored during the current pass. */
	works: number;
	error: string;
	/** Works dropped at the end of the last complete pass. */
	removed?: number;
	run_started?: string;
	updated_at?: string;
	/** Running in the backend process right now. */
	running?: boolean;
}

export interface ActiveModels {
	main: string;
	imslp: string;
	complete: string;
}

/** Matches `app.llm.CredentialStatus`: the secret itself is never sent. */
export interface CredentialStatus {
	set: boolean;
	source: 'admin' | 'env' | '';
	hint: string;
}

export type Credentials = Record<
	'google_api_key' | 'infomaniak_api_key' | 'infomaniak_product_id',
	CredentialStatus
>;

/** A user's report that a score's table of contents is wrong (admin view). */
export interface TocReport {
	id: number;
	score_id: number;
	score_title: string;
	composer: string;
	pdf_path: string;
	username: string;
	comment: string;
	sections: { title: string; page: number; source: string }[];
	resolved: boolean;
	created_at: string;
}
