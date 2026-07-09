export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
	has_document: boolean;
	document_count: number;
}

export interface Citation {
	id: string;
	document_id: string;
	document_name: string;
	page_number: number;
	clause: string | null;
}

export interface Message {
	id: string;
	conversation_id: string;
	role: "user" | "assistant" | "system";
	content: string;
	sources_cited: number;
	message_type: "chat" | "report";
	citations: Citation[];
	confidence?: "high" | "medium" | "low";
	created_at: string;
}

export interface Document {
	id: string;
	conversation_id: string;
	filename: string;
	page_count: number;
	uploaded_at: string;
}

export interface ConversationDetail extends Conversation {
	documents: Document[];
}
