import { BACKEND_URL as BACKEND_URL_ENV } from '$app/env/private';

/** Backend base URL used by all server-side loaders and actions. */
export const BACKEND_URL = BACKEND_URL_ENV || 'http://localhost:8000';
