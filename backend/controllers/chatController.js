const Conversation = require('../models/Conversation');
const fetch = require('node-fetch');

const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://127.0.0.1:8000';

// List user's chats
exports.listChats = async (req, res) => {
	const chats = await Conversation.find({ userId: req.user._id }).sort({ createdAt: -1 });
	res.json(chats);
};

// Create new chat (also create rag session) with graceful failure
exports.createChat = async (req, res) => {
	try {
		// Count existing chats for this user to get next number
		const chatCount = await Conversation.countDocuments({ userId: req.user._id });
		
		const conv = new Conversation({
			userId: req.user._id,
			title: req.body.title || `Chat ${chatCount + 1}`,  // ← Auto-number
			messages: [],
		});

		// try to create session in rag_service (non-fatal)
		try {
			const resp = await fetch(`${RAG_SERVICE_URL}/sessions`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ user_id: req.user._id.toString(), title: conv.title })
			});
			const data = await resp.json();
			if (resp.ok && data.session_id) {
				conv.ragSessionId = data.session_id;
				await conv.save();
			} else {
				console.warn('RAG session creation returned non-ok:', resp.status, data);
			}
		} catch (err) {
			// network error / rag_service down -> log and continue
			console.warn('RAG session creation failed', err && err.message ? err.message : err);
		}

		res.json(conv);
	} catch (e) {
		return res.status(500).json({ message: 'Server error' });
	}
};

// Get chat with messages
exports.getChat = async (req, res) => {
	const { id } = req.params;
	const conv = await Conversation.findById(id);
	if (!conv || conv.userId.toString() !== req.user._id.toString()) return res.status(404).json({ message: 'Not found' });
	res.json(conv);
};

// Add message to chat (user message -> store -> forward to rag_service if available)
exports.addMessage = async (req, res) => {
	const { id } = req.params;
	const { text, evaluate } = req.body;  // ← Extract evaluate flag
	const conv = await Conversation.findById(id);
	if (!conv || conv.userId.toString() !== req.user._id.toString()) return res.status(404).json({ message: 'Not found' });

	// save user message locally
	conv.messages.push({ sender: 'user', text, createdAt: new Date() });
	await conv.save();

	// ensure ragSessionId exists; attempt to create one if missing (non-fatal)
	if (!conv.ragSessionId) {
		try {
			const resp = await fetch(`${RAG_SERVICE_URL}/sessions`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ user_id: req.user._id.toString(), title: conv.title })
			});
			const data = await resp.json();
			if (resp.ok && data.session_id) {
				conv.ragSessionId = data.session_id;
				await conv.save();
			} else {
				console.warn('RAG session creation (on addMessage) non-ok:', resp.status, data);
			}
		} catch (e) {
			console.warn('RAG session creation failed', e && e.message ? e.message : e);
		}
	}

	// Prepare payload for rag_service
	const payload = {
		session_id: conv.ragSessionId || conv._id.toString(),
		user_id: req.user._id.toString(),
		query: text,
		evaluate: !!evaluate,  // ← Pass to rag_service
		include_history: true
	};

	// Attempt to call rag_service /chat; if it fails, return a safe fallback reply
	try {
		const resp = await fetch(`${RAG_SERVICE_URL}/chat`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
		});

		// Check response content-type to handle non-JSON responses
		const contentType = resp.headers.get('content-type');
		
		if (!resp.ok) {
			// Try to parse error as JSON or text
			let errorDetail = `RAG service error ${resp.status}`;
			try {
				if (contentType && contentType.includes('application/json')) {
					const errData = await resp.json();
					errorDetail = errData.detail || errData.message || errorDetail;
				} else {
					const errText = await resp.text();
					errorDetail = errText.substring(0, 500); // truncate long HTML errors
				}
			} catch (parseErr) {
				// ignore parse errors
			}
			console.error('RAG service returned error:', resp.status, errorDetail);
			const assistantText = `Assistant currently unavailable (RAG error: ${resp.status}).`;
			conv.messages.push({ sender: 'assistant', text: assistantText, createdAt: new Date(), debug: { rag_error: errorDetail } });
			await conv.save();
			return res.status(200).json({ assistant: assistantText, conversation: conv });
		}

		// Parse successful JSON response
		let data;
		try {
			data = await resp.json();
		} catch (jsonErr) {
			console.error('RAG service returned non-JSON success response', await resp.text());
			const assistantText = 'Assistant error: invalid response format.';
			conv.messages.push({ sender: 'assistant', text: assistantText, createdAt: new Date() });
			await conv.save();
			return res.status(200).json({ assistant: assistantText, conversation: conv });
		}

		// Use rag response
		const assistantText = data.response || data.response_text || '';
		const debug = data.debug || null;
		const evaluation = data.evaluation || null;  // ← Get evaluation from rag_service

		conv.messages.push({ 
			sender: 'assistant', 
			text: assistantText, 
			createdAt: new Date(), 
			debug,
			evaluation  // ← Store evaluation with message
		});
		await conv.save();

		res.json({ assistant: assistantText, conversation: conv, debug, evaluation });
	} catch (err) {
		// Network-level error (e.g., ECONNREFUSED)
		console.error('Error forwarding to RAG service', err);
		const assistantText = 'Assistant currently unavailable (RAG service unreachable). Please try again later.';
		// save assistant placeholder with debug of error
		conv.messages.push({
			sender: 'assistant',
			text: assistantText,
			createdAt: new Date(),
			debug: { error: err && err.message ? err.message : String(err) }
		});
		await conv.save();
		return res.status(200).json({ assistant: assistantText, conversation: conv });
	}
};

// Delete chat
exports.deleteChat = async (req, res) => {
	const { id } = req.params;
	try {
		const conv = await Conversation.findById(id);
		if (!conv) return res.status(404).json({ message: 'Not found' });
		if (conv.userId.toString() !== req.user._id.toString()) return res.status(403).json({ message: 'Forbidden' });
		await Conversation.findByIdAndDelete(id);
		return res.json({ message: 'Deleted' });
	} catch (err) {
		console.error('Delete chat error', err);
		return res.status(500).json({ message: 'Server error' });
	}
};

// Reset/clear chat messages
exports.resetChat = async (req, res) => {
  const { id } = req.params;
  
  try {
    const conv = await Conversation.findById(id);
    if (!conv || conv.userId.toString() !== req.user._id.toString()) {
      return res.status(404).json({ message: 'Not found' });
    }

    // Call rag_service reset if ragSessionId exists
    if (conv.ragSessionId) {
      try {
        const ragResp = await fetch(`${RAG_SERVICE_URL}/sessions/${conv.ragSessionId}/reset`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        
        if (!ragResp.ok) {
          console.warn('RAG service reset failed:', ragResp.status);
        }
      } catch (err) {
        console.warn('Failed to reset rag session:', err.message);
      }
    }

    // Clear messages in MongoDB
    conv.messages = [];
    await conv.save();

    return res.json({ message: 'Chat cleared', conversation: conv });
  } catch (err) {
    console.error('Reset chat error:', err);
    return res.status(500).json({ message: 'Server error' });
  }
};
