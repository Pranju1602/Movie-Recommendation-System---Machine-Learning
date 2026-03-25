// Navbar background color change on scroll
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// --- CineBot Widget Logic ---
function toggleChatbot() {
    const chatWindow = document.getElementById('cinebot-window');
    if (chatWindow.style.display === 'none' || chatWindow.style.display === '') {
        chatWindow.style.display = 'flex';
        document.getElementById('chat-input').focus();
    } else {
        chatWindow.style.display = 'none';
    }
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendChatMessage();
    }
}

async function sendChatMessage() {
    const inputField = document.getElementById('chat-input');
    const message = inputField.value.trim();
    if (!message) return;
    
    inputField.value = '';
    
    // Render user message
    const chatBody = document.getElementById('chat-body');
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user-message';
    userDiv.textContent = message;
    chatBody.appendChild(userDiv);
    
    // Render typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.id = 'chat-typing';
    typingDiv.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    chatBody.appendChild(typingDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        document.getElementById('chat-typing').remove();
        
        const botDiv = document.createElement('div');
        botDiv.className = 'chat-message bot-message';
        if (data.success) {
            // Replace bold syntax and newlines for sleek markdown rendering
            let formattedStr = data.response.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            botDiv.innerHTML = formattedStr;
        } else {
            botDiv.textContent = "Error: " + (data.error || "Brain offline");
            botDiv.style.color = "#ff4444";
        }
        chatBody.appendChild(botDiv);
        chatBody.scrollTop = chatBody.scrollHeight;
        
    } catch (error) {
        document.getElementById('chat-typing').remove();
        const errDiv = document.createElement('div');
        errDiv.className = 'chat-message bot-message';
        errDiv.textContent = "Network error. I cannot connect to Groq AI.";
        errDiv.style.color = "#ff4444";
        chatBody.appendChild(errDiv);
        chatBody.scrollTop = chatBody.scrollHeight;
    }
}

// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    if (alerts.length > 0) {
        setTimeout(() => {
            alerts.forEach(alert => {
                alert.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px)';
                setTimeout(() => alert.remove(), 600);
            });
        }, 4000);
    }
});
