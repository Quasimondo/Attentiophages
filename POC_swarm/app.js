// app.js - P2P Number Swarm Logic

// -----------------------------------------------------------------------------
// Firebase Configuration (USER ACTION REQUIRED)
// -----------------------------------------------------------------------------
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

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const database = firebase.database();
console.log("Firebase Initialized (ensure you have replaced placeholder config).");

// -----------------------------------------------------------------------------
// DOM Element References
// -----------------------------------------------------------------------------
const localPeerIdDisplay = document.getElementById('local-peer-id');
const peerListUl = document.getElementById('peer-list'); // Corrected from peerList
const localNumberDisplay = document.getElementById('local-number-display');
const generateNumberBtn = document.getElementById('generate-number-btn');
const swarmMaxDisplay = document.getElementById('swarm-max-display');

// -----------------------------------------------------------------------------
// Global Variables
// -----------------------------------------------------------------------------
let localPeerId = null;
const peerConnections = {}; // Stores RTCPeerConnection objects, keyed by remotePeerId
const dataChannels = {};    // Stores RTCDataChannel objects, keyed by remotePeerId
let localNumber = null;
let swarmMaximum = null;
const connectedPeersNumbers = new Map(); // Stores numbers received from peers {peerId: number}

// WebRTC Configuration
const STUN_SERVER = { 'iceServers': [{ 'urls': 'stun:stun.l.google.com:19302' }] };

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------
function generatePeerId() {
    return `user-${Math.random().toString(36).substr(2, 9)}`;
}

function addPeerToUI(peerId) {
    if (!document.getElementById(`peer-${peerId}`)) {
        const listItem = document.createElement('li');
        listItem.id = `peer-${peerId}`;
        listItem.textContent = peerId;
        peerListUl.appendChild(listItem);
    }
}

function removePeerFromUI(peerId) {
    const listItem = document.getElementById(`peer-${peerId}`);
    if (listItem) {
        peerListUl.removeChild(listItem);
    }
}

// -----------------------------------------------------------------------------
// WebRTC Core Functions
// -----------------------------------------------------------------------------
function createPeerConnection(remotePeerId, isInitiator) {
    console.log(`Creating PeerConnection for ${remotePeerId}. Initiator: ${isInitiator}`);
    if (peerConnections[remotePeerId]) {
        console.warn(`PeerConnection for ${remotePeerId} already exists. Closing existing one.`);
        peerConnections[remotePeerId].close();
    }

    const pc = new RTCPeerConnection(STUN_SERVER);
    peerConnections[remotePeerId] = pc;

    pc.onicecandidate = (event) => {
        if (event.candidate) {
            console.log(`Sending ICE candidate to ${remotePeerId}`);
            database.ref(`signaling/${remotePeerId}/iceCandidates/${localPeerId}`).push(event.candidate)
                .catch(err => console.error("Error sending ICE candidate: ", err));
        }
    };

    pc.onconnectionstatechange = () => {
        console.log(`Connection state with ${remotePeerId}: ${pc.connectionState}`);
        if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed' || pc.connectionState === 'closed') {
            handleDisconnect(remotePeerId);
        } else if (pc.connectionState === 'connected') {
            addPeerToUI(remotePeerId);
            if (localNumber !== null) { // Send our number if we already have one
                sendNumberToPeer(remotePeerId, localNumber);
            }
        }
    };

    if (isInitiator) {
        console.log(`Creating DataChannel for ${remotePeerId}`);
        const sendChannel = pc.createDataChannel('sendDataChannel');
        setupDataChannel(sendChannel, remotePeerId);
        dataChannels[remotePeerId] = sendChannel;
    } else {
        pc.ondatachannel = (event) => {
            console.log(`Received DataChannel from ${remotePeerId}`);
            const receiveChannel = event.channel;
            setupDataChannel(receiveChannel, remotePeerId);
            dataChannels[remotePeerId] = receiveChannel;
        };
    }
    return pc;
}

function setupDataChannel(channel, remotePeerId) {
    channel.onopen = () => {
        console.log(`Data channel with ${remotePeerId} opened.`);
        addPeerToUI(remotePeerId); // Ensure peer is in UI once channel is open
        // When channel opens, send current number if available
        if (localNumber !== null) {
            sendNumberToPeer(remotePeerId, localNumber);
        }
    };

    channel.onclose = () => {
        console.log(`Data channel with ${remotePeerId} closed.`);
        // handleDisconnect(remotePeerId); // Handled by onconnectionstatechange
    };

    channel.onmessage = (event) => {
        console.log(`Message received from ${remotePeerId}:`, event.data);
        try {
            const message = JSON.parse(event.data);
            if (message.type === 'number_update') {
                connectedPeersNumbers.set(remotePeerId, message.number);
                console.log(`Updated number for ${remotePeerId}: ${message.number}`);
                calculateAndDisplaySwarmMaximum();
            }
        } catch (error) {
            console.error("Error parsing message from peer:", error);
        }
    };

    channel.onerror = (error) => {
        console.error(`Data channel error with ${remotePeerId}:`, error);
    };
}

function handleDisconnect(remotePeerId) {
    console.log(`Disconnected from ${remotePeerId}`);
    if (peerConnections[remotePeerId]) {
        peerConnections[remotePeerId].close();
        delete peerConnections[remotePeerId];
    }
    if (dataChannels[remotePeerId]) {
        dataChannels[remotePeerId].close();
        delete dataChannels[remotePeerId];
    }
    removePeerFromUI(remotePeerId);
    connectedPeersNumbers.delete(remotePeerId);
    calculateAndDisplaySwarmMaximum(); // Recalculate max without the disconnected peer

    // Clean up Firebase entries related to this disconnected peer (optional, depends on desired cleanup strategy)
    // database.ref(`signaling/${localPeerId}/offers/${remotePeerId}`).remove();
    // database.ref(`signaling/${localPeerId}/answers/${remotePeerId}`).remove();
    // database.ref(`signaling/${localPeerId}/iceCandidates/${remotePeerId}`).remove();
    // database.ref(`signaling/${remotePeerId}/offers/${localPeerId}`).remove();
    // database.ref(`signaling/${remotePeerId}/answers/${localPeerId}`).remove();
    // database.ref(`signaling/${remotePeerId}/iceCandidates/${localPeerId}`).remove();

    console.log(`Cleaned up resources for ${remotePeerId}.`);
}


// -----------------------------------------------------------------------------
// Signaling Logic (Firebase)
// -----------------------------------------------------------------------------
function listenToPeers() {
    const peersRef = database.ref('peers');
    peersRef.on('child_added', (snapshot) => {
        const remotePeerId = snapshot.key;
        if (remotePeerId === localPeerId) return;

        console.log(`Discovered peer: ${remotePeerId}`);
        // Initiate connection if our ID is lexicographically smaller
        if (localPeerId < remotePeerId && !peerConnections[remotePeerId]) {
            console.log(`Initiating connection to ${remotePeerId} (our ID is smaller).`);
            initiateConnectionToPeer(remotePeerId);
        } else {
            console.log(`Will not initiate to ${remotePeerId} (their ID is smaller or connection exists/pending).`);
        }
    });

    peersRef.on('child_removed', (snapshot) => {
        const remotePeerId = snapshot.key;
        if (remotePeerId === localPeerId) return;
        console.log(`Peer ${remotePeerId} left.`);
        handleDisconnect(remotePeerId);
    });

    // Announce our presence
    const localPeerPresenceRef = database.ref(`peers/${localPeerId}`);
    localPeerPresenceRef.set(true).catch(err => console.error("Error announcing presence: ", err));
    localPeerPresenceRef.onDisconnect().remove(); // Remove peer from list if client disconnects abruptly
}

function initiateConnectionToPeer(remotePeerId) {
    if (peerConnections[remotePeerId] && peerConnections[remotePeerId].connectionState === 'connected') {
        console.log(`Already connected to ${remotePeerId}. Skipping initiation.`);
        return;
    }
    const pc = createPeerConnection(remotePeerId, true); // true for initiator
    pc.createOffer()
        .then(offer => {
            console.log(`Created offer for ${remotePeerId}`);
            return pc.setLocalDescription(offer);
        })
        .then(() => {
            console.log(`Sending offer to ${remotePeerId}`);
            return database.ref(`signaling/${remotePeerId}/offers/${localPeerId}`).set(pc.localDescription);
        })
        .catch(error => console.error(`Error initiating connection to ${remotePeerId}:`, error));
}

function listenForOffers() {
    const offersRef = database.ref(`signaling/${localPeerId}/offers`);
    offersRef.on('child_added', (snapshot) => {
        const senderPeerId = snapshot.key;
        const offerData = snapshot.val();

        if (senderPeerId === localPeerId) return; // Ignore self-sent offers (should not happen with this path)

        // If we already have an established or connecting connection, and we are the initiator, ignore subsequent offers.
        // This helps prevent race conditions or redundant connection setups.
        if (peerConnections[senderPeerId] && localPeerId < senderPeerId) {
             console.log(`Ignoring offer from ${senderPeerId} as we are already initiator or connected.`);
             // Clean up the received offer to prevent re-processing if not needed
             // snapshot.ref.remove(); // Be cautious with this, might be too aggressive
             return;
        }

        console.log(`Received offer from ${senderPeerId}:`, offerData);

        let pc = peerConnections[senderPeerId];
        if (!pc || pc.connectionState !== 'connected') { // only create if not connected
            pc = createPeerConnection(senderPeerId, false); // false for receiver
        } else {
             console.log(`Connection to ${senderPeerId} already exists and is connected. Ignoring offer.`);
             return;
        }

        pc.setRemoteDescription(new RTCSessionDescription(offerData))
            .then(() => {
                console.log(`Set remote description for offer from ${senderPeerId}`);
                return pc.createAnswer();
            })
            .then(answer => {
                console.log(`Created answer for ${senderPeerId}`);
                return pc.setLocalDescription(answer);
            })
            .then(() => {
                console.log(`Sending answer to ${senderPeerId}`);
                return database.ref(`signaling/${senderPeerId}/answers/${localPeerId}`).set(pc.localDescription);
            })
            .then(() => {
                // Offer processed, remove it from Firebase to prevent re-processing on page reload by this peer
                snapshot.ref.remove().catch(err => console.warn("Could not remove processed offer:", err));
            })
            .catch(error => {
                console.error(`Error processing offer from ${senderPeerId}:`, error);
                 // If an error occurs, clean up potentially inconsistent state
                handleDisconnect(senderPeerId);
            });
    });
}

function listenForAnswers() {
    const answersRef = database.ref(`signaling/${localPeerId}/answers`);
    answersRef.on('child_added', (snapshot) => {
        const responderPeerId = snapshot.key;
        const answerData = snapshot.val();

        if (!peerConnections[responderPeerId]) {
            console.error(`Received answer from ${responderPeerId}, but no peer connection exists.`);
            return;
        }
        console.log(`Received answer from ${responderPeerId}:`, answerData);

        peerConnections[responderPeerId].setRemoteDescription(new RTCSessionDescription(answerData))
            .then(() => {
                console.log(`Set remote description for answer from ${responderPeerId}`);
                // Answer processed, remove it from Firebase
                snapshot.ref.remove().catch(err => console.warn("Could not remove processed answer:", err));
            })
            .catch(error => console.error(`Error processing answer from ${responderPeerId}:`, error));
    });
}

function listenForIceCandidates() {
    const iceCandidatesRef = database.ref(`signaling/${localPeerId}/iceCandidates`);
    iceCandidatesRef.on('child_added', (parentSnapshot) => { // Iterates over senderPeerIds
        const senderPeerId = parentSnapshot.key;
        parentSnapshot.ref.on('child_added', (childSnapshot) => { // Iterates over candidates from a specific sender
            const candidateData = childSnapshot.val();
            if (!peerConnections[senderPeerId]) {
                console.warn(`Received ICE candidate from ${senderPeerId}, but no peer connection. Might be late.`);
                // Optionally buffer candidates if pc not yet created, then apply once it is.
                return;
            }
            console.log(`Received ICE candidate from ${senderPeerId}:`, candidateData);
            peerConnections[senderPeerId].addIceCandidate(new RTCIceCandidate(candidateData))
                .then(() => {
                    // Candidate added, remove it from Firebase
                    childSnapshot.ref.remove().catch(err => console.warn("Could not remove processed ICE candidate:", err));
                })
                .catch(error => console.error(`Error adding ICE candidate from ${senderPeerId}:`, error));
        });
    });
}

// -----------------------------------------------------------------------------
// Application Logic (Number Generation & Swarm Calculation)
// -----------------------------------------------------------------------------
function generateAndBroadcastNumber() {
    localNumber = Math.floor(Math.random() * 1000) + 1;
    console.log(`Generated new local number: ${localNumber}`);
    localNumberDisplay.textContent = localNumber;

    const message = JSON.stringify({ type: 'number_update', peerId: localPeerId, number: localNumber });
    for (const peerId in dataChannels) {
        if (dataChannels[peerId].readyState === 'open') {
            console.log(`Sending number ${localNumber} to ${peerId}`);
            dataChannels[peerId].send(message);
        } else {
            console.warn(`Data channel with ${peerId} is not open. State: ${dataChannels[peerId].readyState}`);
        }
    }
    calculateAndDisplaySwarmMaximum();
}

function sendNumberToPeer(remotePeerId, number) {
    if (dataChannels[remotePeerId] && dataChannels[remotePeerId].readyState === 'open') {
        const message = JSON.stringify({ type: 'number_update', peerId: localPeerId, number: number });
        console.log(`Sending number ${number} to ${remotePeerId}`);
        dataChannels[remotePeerId].send(message);
    } else {
        console.warn(`Cannot send number to ${remotePeerId}, data channel not open or doesn't exist.`);
    }
}


function calculateAndDisplaySwarmMaximum() {
    let max = localNumber !== null ? localNumber : -Infinity;
    connectedPeersNumbers.forEach((number, peerId) => {
        if (number > max) {
            max = number;
        }
        // Ensure peer is still considered "active" (e.g., data channel open or pc connected)
        if (!dataChannels[peerId] || dataChannels[peerId].readyState !== 'open') {
            // console.warn(`Peer ${peerId} included in max calc but data channel not open.`);
        }
    });
    swarmMaximum = max === -Infinity ? null : max; // Store null if no numbers yet
    swarmMaxDisplay.textContent = swarmMaximum !== null ? swarmMaximum : "N/A";
    console.log(`Swarm maximum calculated: ${swarmMaximum}`);
}


// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------
function initializeApp() {
    console.log("App Initializing...");

    localPeerId = generatePeerId();
    localPeerIdDisplay.textContent = localPeerId;
    console.log(`Local Peer ID: ${localPeerId}`);

    // Initial UI state
    localNumberDisplay.textContent = "Click 'Generate' to start";
    swarmMaxDisplay.textContent = "Waiting for numbers...";

    if (generateNumberBtn) {
        generateNumberBtn.addEventListener('click', generateAndBroadcastNumber);
    } else {
        console.error("Generate New Number button not found.");
    }

    // Start listening for peers and signaling messages
    listenToPeers(); // This will also announce our presence
    listenForOffers();
    listenForAnswers();
    listenForIceCandidates();

    // Generate an initial number for the local peer.
    generateAndBroadcastNumber(); // This will also call calculateAndDisplaySwarmMaximum
}

// Start the application once the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initializeApp);

// Graceful cleanup on window close
window.addEventListener('beforeunload', () => {
    console.log("Cleaning up before unload...");
    if (localPeerId) {
        database.ref(`peers/${localPeerId}`).remove();
        // Optionally, also remove all signaling messages related to this peer
        // database.ref(`signaling/${localPeerId}`).remove(); // This is broad, be careful

        // Close all peer connections
        for (const peerId in peerConnections) {
            handleDisconnect(peerId); // Use existing disconnect logic
        }
    }
});
