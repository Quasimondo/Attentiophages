# WebRTC P2P Number Swarm Demo

## Project Description

This project is a proof-of-concept (PoC) demonstrating a serverless peer-to-peer (P2P) network using WebRTC for direct communication between browsers and a public IRC network (Libera.Chat) for signaling (discovery and connection setup). The application allows peers to connect, each generating a number, and then collaboratively computes and displays the maximum number currently held by any peer in the "swarm."

## IRC Signaling Details

This demo uses the Libera.Chat IRC network (`irc.libera.chat:6697` with SSL) for peer discovery and WebRTC signaling. Peers automatically connect to the channel `#poc-swarm-discovery` upon loading the application.

- **Discovery:** Peers announce their presence and discover others in this IRC channel using `HELLO` messages.
- **Signaling:** WebRTC offers, answers, and ICE candidates are exchanged via private messages between peers over IRC.

No specific IRC client or manual configuration is required from the user, as the application handles the IRC connection internally.

## Running the Demo

1.  Open the `index.html` file directly in a web browser.
2.  To observe the P2P functionality, you need multiple instances of the application running:
    *   Open `index.html` in several browser tabs.
    *   For a more robust test, open `index.html` on different computers. They can be on the same network or different networks (WebRTC's STUN server will help with NAT traversal).

## How to Test / What to Observe

Once you have two or more instances running:

*   **Local Peer ID:** Each instance will display its unique "Your Peer ID".
*   **Connected Peers:** After a brief moment for discovery and connection setup via IRC, other active peer IDs should appear in the "Connected Peers" list on each instance.
*   **Local Number:** Each instance will automatically generate an initial "Your Number". You can click the "Generate New Number" button to generate a new random number for that specific instance. This new number will be broadcast to other connected peers.
*   **Swarm Maximum Number:** The "Swarm Maximum" display should update across all connected peers to show the highest number currently held by any single peer in the group.
*   **Peer Departure:** If you close a tab or browser instance, that peer should disappear from the "Connected Peers" list on other instances. The "Swarm Maximum" will then recalculate based on the remaining peers.

## Troubleshooting

*   **Internet Connectivity:** Ensure you have a stable internet connection.
*   **IRC Network:** The application connects to Libera.Chat. While generally stable, IRC network disruptions could temporarily affect peer discovery. The application has auto-reconnect logic.
*   **Browser Compatibility:** Use a modern web browser that supports WebRTC (e.g., Chrome, Firefox, Edge, Safari).
*   **Firewalls:** While the connection to IRC is typically made over standard SSL ports (similar to HTTPS) when using WebSockets via `irc-framework`, highly restrictive corporate firewalls might still interfere with IRC or WebRTC's STUN/TURN functionalities. If direct P2P connections fail, peers might not connect.
*   **Console Errors:** Open your browser's developer console (usually F12) for error messages related to IRC connection or WebRTC.
*   **NAT Traversal:** WebRTC uses STUN servers (like `stun:stun.l.google.com:19302` configured in this demo) to help peers discover each other across different networks and NATs. While this works in many cases, very restrictive network configurations or firewalls might still prevent direct P2P connections.

## Developer Note: `irc-framework`

The application uses the `irc-framework` JavaScript library to handle IRC communication. For this demo, it's assumed that `IrcFramework` is globally available (e.g., as if included via a `<script>` tag pointing to a browser-compatible bundle). If you are modifying or rebuilding this project, you would typically install `irc-framework` via npm and use a bundler like Webpack or Browserify to include it in the browser-runnable `app.js`.

---
This demo provides a basic framework for P2P communication. Real-world applications would require more robust error handling, potentially TURN servers for more difficult NAT traversal scenarios, and more sophisticated application logic.
