import { setLocale } from '#lib/paraglide/runtime.js';

// French is the app's base locale; tests are written against English text.
setLocale('en', { reload: false });
