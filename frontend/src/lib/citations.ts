import type { Citation } from "../types";

// Matches entire citation blocks: 【...】
const CITATION_BLOCK_REGEX = /【([^】]+)】/g;
// Matches individual page refs within a block
const PAGE_REF_REGEX = /Page\s+(\d+)(?:\s*,\s*(?:Clause|Section)\s+([\w.()]+))?/g;

export interface CitationMatch {
	fullMatch: string;
	documentName: string;
	pageNumber: number;
	clause: string | null;
}

export function parseCitationMarkers(content: string): CitationMatch[] {
	const matches: CitationMatch[] = [];
	const blockRegex = new RegExp(CITATION_BLOCK_REGEX.source, CITATION_BLOCK_REGEX.flags);
	let blockMatch: RegExpExecArray | null;

	while ((blockMatch = blockRegex.exec(content)) !== null) {
		const block = blockMatch[1];
		const parts = block.split("|");
		if (parts.length < 2) continue;

		const docName = parts[0].trim();
		const refsText = parts.slice(1).join("|");
		const pageRegex = new RegExp(PAGE_REF_REGEX.source, PAGE_REF_REGEX.flags);
		let pageMatch: RegExpExecArray | null;

		while ((pageMatch = pageRegex.exec(refsText)) !== null) {
			matches.push({
				fullMatch: blockMatch[0],
				documentName: docName,
				pageNumber: Number.parseInt(pageMatch[1], 10),
				clause: pageMatch[2] || null,
			});
		}
	}
	return matches;
}

export interface ContentSegment {
	type: "text" | "citation";
	text?: string;
	citations?: { citation?: Citation; marker: CitationMatch }[];
	matchedMarker?: CitationMatch;
}

export function splitContentWithCitations(
	content: string,
	citations: Citation[],
): ContentSegment[] {
	const segments: ContentSegment[] = [];
	const blockRegex = new RegExp(CITATION_BLOCK_REGEX.source, CITATION_BLOCK_REGEX.flags);
	let lastIndex = 0;
	let blockMatch: RegExpExecArray | null;

	while ((blockMatch = blockRegex.exec(content)) !== null) {
		// Add text before this citation block
		if (blockMatch.index > lastIndex) {
			segments.push({
				type: "text",
				text: content.slice(lastIndex, blockMatch.index),
			});
		}

		// Parse all page refs within this block
		const block = blockMatch[1];
		const parts = block.split("|");
		if (parts.length < 2) {
			segments.push({ type: "text", text: blockMatch[0] });
			lastIndex = blockMatch.index + blockMatch[0].length;
			continue;
		}

		const docName = parts[0].trim();
		const refsText = parts.slice(1).join("|");
		const pageRegex = new RegExp(PAGE_REF_REGEX.source, PAGE_REF_REGEX.flags);
		let pageMatch: RegExpExecArray | null;
		const citationGroup: { citation?: Citation; marker: CitationMatch }[] = [];

		while ((pageMatch = pageRegex.exec(refsText)) !== null) {
			const marker: CitationMatch = {
				fullMatch: blockMatch[0],
				documentName: docName,
				pageNumber: Number.parseInt(pageMatch[1], 10),
				clause: pageMatch[2] || null,
			};

			// Find matching structured citation from backend
			const matched = citations.find(
				(c) =>
					c.page_number === marker.pageNumber &&
					(c.document_name.toLowerCase().includes(marker.documentName.toLowerCase()) ||
						marker.documentName.toLowerCase().includes(c.document_name.toLowerCase())),
			);

			citationGroup.push({ citation: matched, marker });
		}

		if (citationGroup.length > 0) {
			segments.push({
				type: "citation",
				citations: citationGroup,
			});
		} else {
			segments.push({ type: "text", text: blockMatch[0] });
		}

		lastIndex = blockMatch.index + blockMatch[0].length;
	}

	// Add remaining text
	if (lastIndex < content.length) {
		segments.push({
			type: "text",
			text: content.slice(lastIndex),
		});
	}

	return segments;
}
