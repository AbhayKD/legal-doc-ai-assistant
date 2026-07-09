import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Document } from "../types";

export function useDocuments(conversationId: string | null) {
	const [documents, setDocuments] = useState<Document[]>([]);
	const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
	const [activePage, setActivePage] = useState(1);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		if (!conversationId) {
			setDocuments([]);
			setActiveDocumentId(null);
			return;
		}
		try {
			setError(null);
			const docs = await api.fetchDocuments(conversationId);
			setDocuments(docs);
			if (docs.length > 0) {
				setActiveDocumentId((current) => current ?? docs[0].id);
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load documents");
		}
	}, [conversationId]);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const upload = useCallback(
		async (file: File) => {
			if (!conversationId) return null;
			try {
				setUploading(true);
				setError(null);
				const doc = await api.uploadDocument(conversationId, file);
				setDocuments((prev) => [...prev, doc]);
				setActiveDocumentId(doc.id);
				setActivePage(1);
				return doc;
			} catch (err) {
				setError(
					err instanceof Error ? err.message : "Failed to upload document",
				);
				return null;
			} finally {
				setUploading(false);
			}
		},
		[conversationId],
	);

	const navigateTo = useCallback(
		(documentId: string, page: number) => {
			setActiveDocumentId(documentId);
			const doc = documents.find((d) => d.id === documentId);
			const maxPage = doc?.page_count ?? page;
			setActivePage(Math.max(1, Math.min(page, maxPage)));
		},
		[documents],
	);

	const setPage = useCallback((page: number) => {
		setActivePage(page);
	}, []);

	return {
		documents,
		activeDocumentId,
		activePage,
		uploading,
		error,
		upload,
		navigateTo,
		setPage,
		refresh,
	};
}
