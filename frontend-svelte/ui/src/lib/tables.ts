import {
	columnFilteringFeature,
	createFilteredRowModel,
	createPaginatedRowModel,
	createSortedRowModel,
	filterFn_includesString,
	filterFn_inNumberRange,
	rowPaginationFeature,
	rowSortingFeature,
	sortFn_alphanumeric,
	sortFn_basic,
	sortFn_datetime,
	sortFn_text,
	tableFeatures
} from '@tanstack/svelte-table';

/**
 * What every list table (library, IMSLP results, admin users, success page)
 * uses: client-side filtering, sorting and pagination. TanStack Table v9 only
 * ships what is registered here; the built-ins listed are the ones `'auto'`
 * resolves to for our text, number and date columns.
 */
export const listFeatures = tableFeatures({
	columnFilteringFeature,
	filteredRowModel: createFilteredRowModel(),
	filterFns: { includesString: filterFn_includesString, inNumberRange: filterFn_inNumberRange },
	rowSortingFeature,
	sortedRowModel: createSortedRowModel(),
	sortFns: {
		alphanumeric: sortFn_alphanumeric,
		basic: sortFn_basic,
		datetime: sortFn_datetime,
		text: sortFn_text
	},
	rowPaginationFeature,
	paginatedRowModel: createPaginatedRowModel()
});

export type ListFeatures = typeof listFeatures;
