export const warn = import.meta.env.DEV
	? console.warn.bind(console)
	: () => {};

export const error = import.meta.env.DEV
	? console.error.bind(console)
	: () => {};
