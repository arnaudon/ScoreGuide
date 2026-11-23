import { composerName } from '#lib/library.js';

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

/**
 * The video id in a YouTube link (watch?v=, youtu.be/, /embed/, /shorts/,
 * /live/), or null when it isn't a YouTube video link.
 */
export function youtubeVideoId(url: string | null | undefined): string | null {
	let parsed: URL;
	try {
		parsed = new URL((url ?? '').trim());
	} catch {
		return null;
	}
	const host = parsed.hostname.replace(/^(www|m|music)\./, '');
	let id: string | null = null;
	if (host === 'youtu.be') {
		id = parsed.pathname.split('/')[1] ?? null;
	} else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
		const [, kind, value] = parsed.pathname.split('/');
		id =
			kind === 'watch'
				? parsed.searchParams.get('v')
				: ['embed', 'shorts', 'live'].includes(kind)
					? value
					: null;
	}
	return id && VIDEO_ID.test(id) ? id : null;
}

/** YouTube's privacy-enhanced player for a video, started on load (the user clicked Play). */
export function youtubeEmbedUrl(id: string): string {
	return `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
}

/** YouTube search results for a piece: many performances to choose from. */
export function youtubeSearchUrl(composer: string, title: string): string {
	const query = [composerName(composer ?? ''), title ?? ''].join(' ').replace(/\s+/g, ' ').trim();
	return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}
