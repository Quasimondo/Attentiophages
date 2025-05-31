# WebRTC P2P Number Swarm Demo

## Project Description

This project is a proof-of-concept (PoC) demonstrating a serverless peer-to-peer (P2P) network using WebRTC for direct communication between browsers and Firebase Realtime Database for signaling (discovery and connection setup). The application allows peers to connect, each generating a number, and then collaboratively computes and displays the maximum number currently held by any peer in the "swarm."

## Firebase Setup Instructions

To run this demo, you'll need to configure it with your own Firebase project.

1.  **Go to Firebase:** Open the [Firebase console](https://firebase.google.com/).
2.  **Create/Select Project:** Create a new Firebase project or select an existing one.
3.  **Enable Realtime Database:**
    *   In your project, navigate to "Build" > "Realtime Database" from the left-hand menu.
    *   Click "Create Database".
    *   Select a region for your database.
    *   For security rules, choose **"Start in test mode"**. This will allow open read/write access.
        *   **Important Note:** Test mode is suitable only for this PoC and short-term development. Production applications require secure database rules.
        ```json
        // Example Test Mode Rules (auto-applied when you select test mode)
        {
          "rules": {
            ".read": true,
            ".write": true
          }
        }
        ```
4.  **Add a Web App to your Firebase Project:**
    *   Go back to "Project Overview" (click the Firebase icon or "Project Overview" in the top left).
    *   Click the gear icon next to "Project Overview" to go to "Project settings".
    *   Under the "General" tab, in the "Your apps" section, click the web icon (`</>`).
    *   Enter an "App nickname" (e.g., "WebRTC P2P Demo") and click "Register app". Firebase Hosting is not needed for this demo.
5.  **Get Firebase Configuration:**
    *   After registering, Firebase will display a `firebaseConfig` object. This object contains the necessary keys and IDs to connect your application to your Firebase project.
    *   Copy this entire `firebaseConfig` object. It will look something like this:
        ```javascript
        const firebaseConfig = {
          apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXX",
          authDomain: "your-project-id.firebaseapp.com",
          databaseURL: "https://your-project-id-default-rtdb.firebaseio.com",
          projectId: "your-project-id",
          storageBucket: "your-project-id.appspot.com",
          messagingSenderId: "000000000000",
          appId: "1:000000000000:web:XXXXXXXXXXXXXXXXXXXXXX"
        };
        ```

## Configuration in `app.js`

1.  Open the `app.js` file in this project.
2.  Locate the placeholder `firebaseConfig` object at the beginning of the file:
    ```javascript
    // TODO: Replace with your actual Firebase project configuration
    const firebaseConfig = {
        apiKey: "YOUR_API_KEY",
        authDomain: "YOUR_AUTH_DOMAIN",
        databaseURL: "YOUR_DATABASE_URL", // Make sure this is the Realtime Database URL
        projectId: "YOUR_PROJECT_ID",
        storageBucket: "YOUR_STORAGE_BUCKET",
        messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
        appId: "YOUR_APP_ID"
    };
    ```
3.  Replace this entire placeholder object with the `firebaseConfig` object you copied from your Firebase project settings.

## Running the Demo

1.  Ensure you have updated `app.js` with your Firebase configuration.
2.  Open the `index.html` file directly in a web browser.
3.  To observe the P2P functionality, you need multiple instances of the application running and connected to the **same Firebase project configuration**:
    *   Open `index.html` in several browser tabs.
    *   For a more robust test, open `index.html` on different computers. They can be on the same network or different networks (WebRTC's STUN server will help with NAT traversal).

## How to Test / What to Observe

Once you have two or more instances running:

*   **Local Peer ID:** Each instance will display its unique "Your Peer ID".
*   **Connected Peers:** After a brief moment for discovery and connection setup via Firebase, other active peer IDs should appear in the "Connected Peers" list on each instance.
*   **Local Number:** Each instance will automatically generate an initial "Your Number". You can click the "Generate New Number" button to generate a new random number for that specific instance. This new number will be broadcast to other connected peers.
*   **Swarm Maximum Number:** The "Swarm Maximum" display should update across all connected peers to show the highest number currently held by any single peer in the group.
*   **Peer Departure:** If you close a tab or browser instance, that peer should disappear from the "Connected Peers" list on other instances. The "Swarm Maximum" will then recalculate based on the remaining peers.

## Troubleshooting

*   **Firebase Rules:** Double-check that your Firebase Realtime Database rules are set to allow reads and writes. For testing, they should be:
    ```json
    {
      "rules": {
        ".read": true,
        ".write": true
      }
    }
    ```
    You can edit these in the Firebase console under "Realtime Database" > "Rules".
*   **Console Errors:** Open your browser's developer console (usually by pressing F12) and check for any error messages. Errors related to Firebase (e.g., configuration issues, permissions) or WebRTC (e.g., connection failures) will appear here.
*   **Firebase Configuration:** Ensure the `firebaseConfig` object in `app.js` is correctly copied from your Firebase project and that `databaseURL` is the URL for your Realtime Database.
*   **NAT Traversal:** WebRTC uses STUN servers (like `stun:stun.l.google.com:19302` configured in this demo) to help peers discover each other across different networks and NATs. While this works in many cases, very restrictive network configurations or firewalls might still prevent direct P2P connections.
*   **Same Firebase Project:** All instances of the demo *must* be configured with the exact same `firebaseConfig` to communicate.

---
This demo provides a basic framework for P2P communication. Real-world applications would require more robust error handling, secure database rules, potentially TURN servers for more difficult NAT traversal scenarios, and more sophisticated application logic.
