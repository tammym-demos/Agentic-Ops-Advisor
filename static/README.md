# Chat UI for Agentic Ops Advisor

This directory contains the browser-based chat interface for the Agentic Ops Advisor hosted agent.

## Files

- **index.html** — Single-page chat application with no external dependencies

## Features

- ✅ Clean, responsive chat interface
- ✅ Real-time interaction with the agent via the Foundry Responses API
- ✅ Multi-turn conversation support (thread management)
- ✅ Quick prompt buttons for common queries
- ✅ Connection status indicator
- ✅ Error handling and display
- ✅ Simple markdown-like formatting (code blocks, inline code)
- ✅ Typing indicators during agent processing
- ✅ Auto-resizing message input

## Usage

1. Start the server:
   ```bash
   python scripts/serve.py
   ```

2. Open your browser to:
   ```
   http://localhost:8088/
   ```

3. The UI will automatically connect to the `/responses` endpoint on the same host.

## API Integration

The chat UI communicates with the Foundry Responses API protocol (v1):

- **Endpoint**: `POST /responses`
- **Request**: 
  ```json
  {
    "input": {
      "messages": [
        { "role": "user", "content": "Your question here" }
      ]
    },
    "thread_id": "optional-thread-id"
  }
  ```
- **Response**:
  ```json
  {
    "id": "resp_abc123",
    "object": "response",
    "output": [
      { "type": "message", "role": "assistant", "content": "Agent response" }
    ],
    "status": "completed",
    "thread_id": "thread-abc123"
  }
  ```

## Thread Management

The UI maintains conversation continuity by:
1. Creating a new thread on first message
2. Storing the `thread_id` from the response
3. Including the `thread_id` in subsequent requests

This allows multi-turn conversations where the agent maintains context across messages.

## Customization

The UI is a single HTML file with inline CSS and JavaScript. To customize:

- **Styling**: Edit the `:root` CSS variables for color scheme
- **Quick Prompts**: Update the `.quick-prompts` section in the HTML
- **API Endpoint**: Modify `API_BASE` constant in the JavaScript (defaults to window.location.origin)

## Production Deployment

For production:

1. Update CORS settings in `scripts/serve.py` to restrict allowed origins
2. Add authentication/authorization as needed
3. Consider adding HTTPS termination via reverse proxy
4. Add rate limiting and request validation

## Browser Compatibility

Works in all modern browsers (Chrome, Firefox, Safari, Edge). Requires:
- ES6 JavaScript support
- Fetch API
- CSS Grid and Flexbox

No polyfills or build step required.
