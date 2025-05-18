document.addEventListener("DOMContentLoaded", () => {
    const chatBox = document.getElementById("chat-box");

    if (typeof heroReplies !== "object" || heroReplies === null) return;

    const delayPerHero = 2500; // 2.5 seconds per reply
    const heroes = Object.keys(heroReplies);
    let i = 0;

    function typeNextHero() {
        if (i < heroes.length) {
            const hero = heroes[i];
            const msg = heroReplies[hero];

            const typingDiv = document.createElement("div");
            typingDiv.id = `typing-${hero}`;
            typingDiv.innerHTML = `<em>${hero} is typing...</em>`;
            chatBox.appendChild(typingDiv);
            chatBox.scrollTop = chatBox.scrollHeight;

            setTimeout(() => {
                typingDiv.remove();
                const msgDiv = document.createElement("div");
                msgDiv.className = "mb-3";
                msgDiv.innerHTML = `<strong>${hero}:</strong> ${msg}`;
                chatBox.appendChild(msgDiv);
                chatBox.scrollTop = chatBox.scrollHeight;

                i++;
                typeNextHero();
            }, delayPerHero);
        }
    }

    typeNextHero();
});

