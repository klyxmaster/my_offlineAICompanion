// Automatically enable dark mode when the page loads
window.addEventListener('DOMContentLoaded', function() {
    document.body.classList.add('dark-mode');
    document.querySelector('.container').classList.add('dark-mode');
    document.querySelector('.left-side').classList.add('dark-mode');
    document.querySelector('.right-side').classList.add('dark-mode');
    document.querySelector('textarea').classList.add('dark-mode');
    document.getElementById('theme-toggle').classList.add('dark-mode');
});

// Attach the input event listener to the textarea for auto-resizing
document.getElementById('user-input').addEventListener('input', autoResizeTextarea);

// Listen for "Enter" key press to send prompt (textarea)
document.getElementById('user-input').addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        sendPrompt();
    }
});

// Send button functionality (make sure the button is linked properly)
document.getElementById('send-button').addEventListener('click', function() {
    sendPrompt();
});

// Function to send user input as a prompt and handle AI response
async function sendPrompt() {
    const inputField = document.getElementById('user-input');
    const userInput = inputField.value;

    if (userInput.trim() === "") return;  // Ensure non-empty input

    inputField.value = '';  // Clear input field
    inputField.style.height = '55px';  // Reset height for resizing
    inputField.focus();

    appendUserMessage(userInput);  // Display user's message in the chat

    // Add assistant typing animation before making the fetch request
    let assistantDiv = appendAssistantTyping();  // Add typing animation with "Sarah is typing..."

    try {
        console.log("Sending request to backend...");  // Log the start of the request

        const response = await fetch('http://127.0.0.1:8000/send_prompt/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt: userInput })  // Send user input as JSON
        });

        console.log("Response received from backend:", response);  // Log the response

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.text();  // Expecting plain text response
        console.log("Parsed response from backend:", result);  // Log the parsed response

        removeTypingDots(assistantDiv);  // Remove typing animation
        appendAssistantMessage(result);  // Append AI response
    } catch (error) {
        console.error("Fetch error:", error);  // Log fetch errors in the console
        removeTypingDots(assistantDiv);
        appendAssistantMessage("Unable to reach the server. Please try again.");
    }
}

// Function to append user message to the chatbox
function appendUserMessage(message) {
    const chatBox = document.querySelector('.chat-box');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'message-user');
    messageDiv.textContent = message;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom
}

// Function to append AI's typing animation (Sarah is typing with animated dots)
function appendAssistantTyping() {
    const chatBox = document.querySelector('.chat-box');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'message-bot');

    // Add the typing animation HTML
    messageDiv.innerHTML = `
        <div class="typing-animation">
            Sarah is typing
            <div class="typing-dots">
                <span>.</span><span>.</span><span>.</span>
            </div>
        </div>
    `;

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom
    return messageDiv;
}

// Function to append AI's response
function appendAssistantMessage(message) {
    const chatBox = document.querySelector('.chat-box');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'message-bot');
    messageDiv.textContent = message;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Function to remove typing animation (after the response is received)
function removeTypingDots(typingDiv) {
    typingDiv.remove();
}

// Function to auto resize textarea as user types
function autoResizeTextarea() {
    const textarea = document.getElementById('user-input');
    textarea.style.height = 'auto';  // Reset the height to auto to shrink if necessary
    textarea.style.height = (textarea.scrollHeight) + 'px';  // Adjust the height based on content
}
