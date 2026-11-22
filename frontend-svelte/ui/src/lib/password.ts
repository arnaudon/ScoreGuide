/** Same bounds as the backend's `Password` type (app/users.py). */
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

/** Whether a new password is long enough (and not absurdly long). */
export function passwordLengthOk(password: string): boolean {
	return password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH;
}
